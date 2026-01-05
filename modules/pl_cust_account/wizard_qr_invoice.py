# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.wizard import Wizard, StateView, StateTransition, StateAction, Button
from trytond.model import ModelView, fields
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.transaction import Transaction

from decimal import Decimal
from datetime import date, date as _date
import base64
import logging
import re
import calendar as _cal
import signal

import numpy as np
import cv2
from pdf2image import convert_from_bytes
from pyzbar.pyzbar import decode as zbar_decode
from PIL import Image


__all__ = [
    'QrInvoiceError', 'QrInvoiceStart',
    'QrInvoiceConfirm', 'QrInvoiceWizard'
]


logger = logging.getLogger(__name__)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False


_MAX_QR_PREVIEW = 140
_IBAN_CH_RE = re.compile(r'(?:CH|LI)\d{2}[0-9A-Z]{17}', re.I)


class QrInvoiceError(ValidationError):
    pass


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

# Ajoute ça près du haut du fichier
_QR_LINE_SEPS = {
    '\x1d',  # GS
    '\x1e',  # RS
    '\x1f',  # US
    '\x0b',  # VT
    '\x0c',  # FF
    '\u2028',  # unicode line sep
    '\u2029',  # unicode paragraph sep
}

def _clean_qr_text(s: str) -> str:
    """
    Normalise le texte QR:
    - enlève BOM / NUL
    - convertit des séparateurs (GS/RS/US/VT/FF/2028/2029) en '\n'
    - normalise \r\n et \r
    - remplace les autres contrôles par des espaces
    """
    if not s:
        return ''

    # BOM + NUL fréquents avec ECI/UTF-16
    s = s.replace('\ufeff', '').replace('\x00', '')

    # séparateurs “bizarres” → newline
    for sep in _QR_LINE_SEPS:
        s = s.replace(sep, '\n')

    # normalize newlines
    s = s.replace('\r\n', '\n').replace('\r', '\n')

    # autres contrôles
    s = ''.join(ch if (ord(ch) >= 32 or ch in '\n\t') else ' ' for ch in s)

    return s.strip()


def _normalize_iban(iban: str) -> str:
    return re.sub(r'\s+', '', (iban or '')).upper()


def _decode_binary_input(data_obj):
    """
    Tryton Binary fields can arrive as:
      - dict {'filename': ..., 'data': ...}
      - bytes / bytearray
      - base64 string
    Return (filename, pdf_bytes).
    """
    filename = None

    if isinstance(data_obj, dict):
        filename = data_obj.get('filename') or None
        data = data_obj.get('data') or b''
        if isinstance(data, str):
            data = base64.b64decode(data)
    elif isinstance(data_obj, (bytes, bytearray)):
        data = data_obj
    elif isinstance(data_obj, str):
        data = base64.b64decode(data_obj)
    else:
        raise QrInvoiceError("Format invalide (champ binaire).")

    if not isinstance(data, (bytes, bytearray)):
        raise QrInvoiceError("Format invalide (bytes attendus).")

    return filename, data


def _ensure_fiscalyear(pool, dt):
    FiscalYear = pool.get('account.fiscalyear')
    Company = pool.get('company.company')
    cid = Transaction().context.get('company')
    company = Company(cid) if cid else None

    fy = FiscalYear.search(
        [('start_date', '<=', dt), ('end_date', '>=', dt)]
        + ([('company', '=', company)] if company else []),
        limit=1
    )
    if fy:
        return fy[0]

    template, = FiscalYear.search(
        ([('company', '=', company)] if company else []),
        order=[('end_date', 'DESC')], limit=1
    ) or [None]
    if not template:
        raise QrInvoiceError("Aucun exercice fiscal modèle disponible.")

    seq_field = next(
        (n for n in ('post_move_sequence', 'move_sequence', 'sequence')
         if n in getattr(FiscalYear, '_fields', {})),
        None
    )
    if not seq_field:
        raise QrInvoiceError("Champ séquence absent sur l'exercice fiscal.")

    try:
        Seq = pool.get('ir.sequence.strict')
    except KeyError:
        Seq = pool.get('ir.sequence')

    year = dt.year
    vals_seq = {'name': f'Mouvements {year}', 'prefix': f'{year}-', 'padding': 5}
    if 'company' in getattr(Seq, '_fields', {}) and company:
        vals_seq['company'] = company
    if 'sequence_type' in getattr(Seq, '_fields', {}):
        tseq = getattr(template, seq_field)
        if not tseq or 'sequence_type' not in getattr(type(tseq), '_fields', {}):
            raise QrInvoiceError("Type de séquence introuvable pour auto-création.")
        vals_seq['sequence_type'] = tseq.sequence_type
    else:
        if 'code' in getattr(Seq, '_fields', {}):
            vals_seq['code'] = 'account.move'

    seq, = Seq.create([vals_seq])

    vals_fy = {
        'name': f'Exercice {year}',
        'start_date': date(year, 1, 1),
        'end_date': date(year, 12, 31),
        seq_field: seq,
    }
    if 'company' in FiscalYear._fields and company:
        vals_fy['company'] = company
    fy, = FiscalYear.create([vals_fy])
    logger.info("FY auto-créé: id=%s", fy.id)
    return fy


def _ensure_period(pool, dt):
    Period = pool.get('account.period')
    per = Period.search([('start_date', '<=', dt), ('end_date', '>=', dt)], limit=1)
    if per:
        return per[0]

    fy = _ensure_fiscalyear(pool, dt)
    start = _date(dt.year, dt.month, 1)
    end = _date(dt.year, dt.month, _cal.monthrange(dt.year, dt.month)[1])

    if start < fy.start_date:
        start = fy.start_date
    if end > fy.end_date:
        end = fy.end_date

    per, = Period.create([{
        'name': dt.strftime('%B %Y').capitalize(),
        'start_date': start,
        'end_date': end,
        'fiscalyear': fy,
    }])
    logger.info("Période auto-créée: id=%s", per.id)
    return per


def _find_account_by_kind(pool, wanted_kind):
    Account = pool.get('account.account')

    if 'kind' in Account._fields:
        acc = Account.search([('kind', '=', wanted_kind)], limit=1)
        if acc:
            return acc[0]

    if 'type' in Account._fields:
        try:
            AType = pool.get('account.account.type')
        except KeyError:
            AType = None
        if AType and 'kind' in AType._fields:
            t = AType.search([('kind', '=', wanted_kind)], limit=1)
            if t:
                acc = Account.search([('type', '=', t[0].id)], limit=1)
                if acc:
                    return acc[0]
    return None


def _find_unit(pool):
    for model in ('product.uom', 'uom.uom'):
        try:
            Uom = pool.get(model)
        except KeyError:
            continue
        u = Uom.search([('symbol', 'in', ['u', 'unit', 'Unit'])], limit=1) \
            or Uom.search([('name', 'ilike', 'unit')], limit=1)
        if u:
            return u[0]
    return None


# ---------------------------------------------------------------------------
# Party matching + auto creation/completion (YOUR MAIN REQUEST)
# ---------------------------------------------------------------------------

def _match_party_by_iban(pool, iban):
    if not iban:
        return None
    Party = pool.get('party.party')
    num = _normalize_iban(iban)

    # try short tail match first then full match variants
    cands = Party.search([('iban', 'ilike', f'%{num[-10:]}%')], limit=10)
    if not cands:
        cands = Party.search([('iban', 'ilike', f'%{num}%')], limit=10)
        if not cands:
            spaced = ' '.join([num[i:i + 4] for i in range(0, len(num), 4)])
            cands = Party.search([('iban', 'ilike', f'%{spaced}%')], limit=10)

    for p in cands:
        if _normalize_iban(getattr(p, 'iban', '') or '') == num:
            return p
    return cands[0] if cands else None


def _match_party_by_name(pool, label):
    if not label:
        return None
    Party = pool.get('party.party')

    # In your pl_cust_plbase, company name is stored in lastname (required=True)
    if 'lastname' in Party._fields:
        res = Party.search([('lastname', 'ilike', label)], limit=1) \
            or Party.search([('name', 'ilike', label)], limit=1)
    else:
        res = Party.search([('name', 'ilike', label)], limit=1)

    return res[0] if res else None


def _ensure_supplier_party(pool, creditor_name: str, iban: str):
    """
    Find supplier by IBAN or name. If missing -> create.
    Enforce moral person (company): is_person_moral=True.
    Also enforces lastname/name, party_type='f', and fills IBAN if empty.
    """
    Party = pool.get('party.party')
    label = (creditor_name or '').strip() or 'QR'
    iban_norm = (iban or '').strip()

    party = _match_party_by_iban(pool, iban_norm) if iban_norm else None
    if not party:
        party = _match_party_by_name(pool, label)

    if not party:
        vals = {}

        if 'is_person_moral' in Party._fields:
            vals['is_person_moral'] = True

        # your module makes lastname required -> store company label there
        if 'lastname' in Party._fields:
            vals['lastname'] = label
            # prevent “person” fields being filled
            if 'firstname' in Party._fields:
                vals['firstname'] = ''
            if 'party_title' in Party._fields:
                vals['party_title'] = ''
        else:
            vals['name'] = label

        if 'iban' in Party._fields and iban_norm:
            vals['iban'] = iban_norm

        if 'party_type' in Party._fields:
            vals['party_type'] = 'f'

        party, = Party.create([vals])
        logger.info("Party créé automatiquement: id=%s, label=%s", party.id, label)
        return party

    # Party exists -> complete/normalize
    write_vals = {}

    if 'is_person_moral' in Party._fields and not getattr(party, 'is_person_moral', False):
        write_vals['is_person_moral'] = True
        if 'firstname' in Party._fields:
            write_vals['firstname'] = None
        if 'party_title' in Party._fields:
            write_vals['party_title'] = ''

    # Ensure required lastname is not empty (some legacy parties can be broken)
    if 'lastname' in Party._fields:
        ln = (getattr(party, 'lastname', '') or '').strip()
        if not ln:
            write_vals['lastname'] = label

    if 'iban' in Party._fields and iban_norm:
        current = (getattr(party, 'iban', '') or '').strip()
        if not current:
            write_vals['iban'] = iban_norm

    if 'party_type' in Party._fields:
        cur = getattr(party, 'party_type', None)
        if not cur:
            write_vals['party_type'] = 'f'

    if write_vals:
        Party.write([party], write_vals)
        logger.info("Party complété: id=%s (%s)", party.id, ", ".join(write_vals.keys()))

    return party


def _ensure_supplier_address(pool, party, parsed: dict):
    """
    Ensure supplier has at least one address.
    Create using your custom address fields when present.
    """
    Address = pool.get('party.address')

    addr = Address.search(
        [('party', '=', party.id)],
        order=[('sequence', 'ASC'), ('id', 'ASC')],
        limit=1
    )
    if addr:
        return addr[0]

    street = (parsed.get("creditor_address") or "").strip()
    zip_code = (parsed.get("creditor_zip") or "").strip()
    city = (parsed.get("creditor_city") or "").strip()
    country_code = (parsed.get("creditor_country") or "").strip()

    if not street and not zip_code and not city:
        street = "Adresse inconnue"

    vals = {'party': party.id}

    if 'invoice' in Address._fields:
        vals['invoice'] = True

    if 'addr_street' in Address._fields:
        vals['addr_street'] = street
    elif 'street' in Address._fields:
        vals['street'] = street

    if 'postal_code' in Address._fields:
        vals['postal_code'] = zip_code
    if 'city' in Address._fields:
        vals['city'] = city

    if country_code and 'country' in Address._fields:
        try:
            Country = pool.get("country.country")
            res = Country.search([("code", "=", country_code)], limit=1) \
                or Country.search([("name", "ilike", country_code)], limit=1)
            if res:
                vals["country"] = res[0].id
        except Exception:
            pass

    address, = Address.create([vals])
    logger.info("Adresse créée automatiquement: id=%s pour party id=%s", address.id, party.id)
    return address


# ---------------------------------------------------------------------------
# QR decode + SPC parsing
# ---------------------------------------------------------------------------

class TimeoutException(Exception):
    pass


def _signal_handler(signum, frame):
    raise TimeoutException("QR decoding timeout")


def _low_level_decode(img_bgr):
    out = []

    signal.signal(signal.SIGALRM, _signal_handler)
    signal.alarm(3)

    try:
        det = cv2.QRCodeDetector()

        def push(s):
            s = (s or '').strip()
            if s and len(s) >= 20 and s not in out:
                out.append(s)

        try:
            s, _, _ = det.detectAndDecode(img_bgr)
            push(s)
        except Exception as e:
            logger.debug("detectAndDecode error: %s", e, exc_info=True)

        try:
            ok, data_list, _, _ = det.detectAndDecodeMulti(img_bgr)
            if ok and data_list:
                for s in data_list:
                    push(s)
        except Exception as e:
            logger.debug("detectAndDecodeMulti error: %s", e, exc_info=True)

        try:
            pil = Image.fromarray(img_bgr[:, :, ::-1])
            for r in zbar_decode(pil):
                try:
                    txt = r.data.decode('utf-8')
                except UnicodeDecodeError:
                    txt = r.data.decode('latin-1', errors='replace')
                push(txt)
        except Exception as e:
            logger.debug("pyzbar decode error: %s", e, exc_info=True)

        signal.alarm(0)
        return out

    except TimeoutException:
        logger.warning("QR decode timeout → abandon du scan")
        signal.alarm(0)
        return []

    except Exception as e:
        logger.error("Erreur QR: %s", e, exc_info=True)
        signal.alarm(0)
        return []


def _split_spc_lines(block: str):
    block = _clean_qr_text(block)
    lines = block.split('\n')

    # enlève vides au début
    while lines and not lines[0].strip():
        lines.pop(0)

    # enlève vides à la fin
    while lines and not lines[-1].strip():
        lines.pop()

    return lines



def is_valid_spc_block(block: str) -> bool:
    if not block:
        return False

    block = _clean_qr_text(block)
    lines = _split_spc_lines(block)
    if not lines:
        return False

    # trouver la ligne "SPC" même si elle n’est pas en position 0
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "SPC")
    except StopIteration:
        return False

    lines = lines[start:]
    if len(lines) < 10:
        return False

    # lignes fixes
    if lines[0].strip() != "SPC":
        return False

    version = lines[1].strip()
    if not re.match(r'^\d{4}$', version):
        return False

    coding = lines[2].strip()
    if coding not in ("1", ""):
        return False

    # IBAN: on cherche dans tout le bloc (plus robuste)
    if not _IBAN_CH_RE.search(block):
        return False

    txt = "\n".join(lines)
    if not any(t in txt for t in ("QRR", "SCOR", "NON")):
        return False
    if "EPD" not in txt:
        return False

    return True


def _parse_spc_dynamic(content: str) -> dict:
    data = {
        "iban": "",
        "creditor_name": "",
        "creditor_address": "",
        "creditor_zip": "",
        "creditor_city": "",
        "creditor_country": "",
        "amount": "",
        "currency": "",
        "reference": "",
        "reference_type": "",
        "unstructured_message": "",
        "billing_information": "",
        "alt_schemes": [],
        "full_text": content or "",
    }

    if not content:
        return data

    lines = _split_spc_lines(content)
    non_empty = [l.strip() for l in lines if l.strip()]

    try:
        if lines and lines[0].strip() == "SPC" and len(non_empty) >= 10:
            l = list(lines) + [""] * 40

            flat = "\n".join(l)
            iban_line = l[3].strip()
            m_iban = _IBAN_CH_RE.search(iban_line) or _IBAN_CH_RE.search(flat)
            if m_iban:
                data["iban"] = m_iban.group(0)

            addr_type = l[4].strip()
            name = l[5].strip()
            data["creditor_name"] = name

            if addr_type == "K":
                addr_line = l[6].strip()
                zip_city_line = l[7].strip()
                data["creditor_address"] = addr_line
                m = re.match(r"(\d{3,10})\s+(.+)", zip_city_line)
                if m:
                    data["creditor_zip"] = m.group(1)
                    data["creditor_city"] = m.group(2)
                else:
                    data["creditor_city"] = zip_city_line
                country = l[10].strip() or l[8].strip()
                data["creditor_country"] = country

            elif addr_type == "S":
                street = l[6].strip()
                number = l[7].strip()
                data["creditor_address"] = f"{street} {number}".strip()
                data["creditor_zip"] = l[8].strip()
                data["creditor_city"] = l[9].strip()
                data["creditor_country"] = l[10].strip()

            amount = l[18].strip()
            currency = l[19].strip()
            if currency in ("CHF", "EUR"):
                data["currency"] = currency

            norm_amount = amount.replace("'", "").replace(" ", "").replace(",", ".")
            if re.match(r"^\d{1,12}(\.\d{1,2})?$", norm_amount):
                data["amount"] = amount

            ref_type = ""
            ref = ""
            ref_index = None
            for idx, line in enumerate(l):
                t = line.strip()
                if t in ("QRR", "SCOR", "NON"):
                    ref_type = t
                    ref_index = idx
                    if idx + 1 < len(l):
                        ref = l[idx + 1].strip()
                    break

            data["reference_type"] = ref_type
            if ref_type and ref_type != "NON":
                data["reference"] = ref

            msg = ""
            if ref_index is not None:
                for j in range(ref_index + 2, len(l)):
                    t = l[j].strip()
                    if t and t != "EPD":
                        msg = t
                        break
            data["unstructured_message"] = msg

            billing_information = ""
            alt_schemes = []
            for j, line in enumerate(l):
                if line.strip() == "EPD":
                    if j + 1 < len(l):
                        billing_information = l[j + 1].strip()
                    if j + 2 < len(l):
                        alt_schemes = [
                            x.strip() for x in l[j + 2:]
                            if x.strip() and x.strip() not in ("AP1", "AP2")
                        ]
                    break
            data["billing_information"] = billing_information
            data["alt_schemes"] = alt_schemes

            logger.info(
                "SPC parsed → IBAN=%s, Creditor=%s, Amount=%s, Ref=%s (%s)",
                data.get("iban"),
                data.get("creditor_name"),
                data.get("amount"),
                data.get("reference"),
                data.get("reference_type"),
            )
            return data

    except Exception as e:
        logger.debug("SPC strict parse failed, fallback: %s", e, exc_info=True)

    # Fallback: best-effort extraction
    raw = content.replace("\r", "\n").split("\n")
    lines = [l.strip() for l in raw if l.strip()]

    iban = ""
    for l_ in lines:
        m = _IBAN_CH_RE.search(l_)
        if m:
            iban = m.group(0)
            break
    data["iban"] = iban

    addr_type = None
    idx_addr = None
    for i, l_ in enumerate(lines):
        if l_ in ("K", "S"):
            addr_type = l_
            idx_addr = i
            break

    if addr_type == "K":
        name = lines[idx_addr + 1] if idx_addr + 1 < len(lines) else ""
        addr = lines[idx_addr + 2] if idx_addr + 2 < len(lines) else ""
        zip_city = lines[idx_addr + 3] if idx_addr + 3 < len(lines) else ""
        country = lines[idx_addr + 4] if idx_addr + 4 < len(lines) else ""

        m = re.match(r"(\d{3,10})\s+(.+)", zip_city)
        if m:
            zip_code = m.group(1)
            city = m.group(2)
        else:
            zip_code = ""
            city = zip_city

        data["creditor_name"] = name
        data["creditor_address"] = addr
        data["creditor_zip"] = zip_code
        data["creditor_city"] = city
        data["creditor_country"] = country

    elif addr_type == "S":
        name = lines[idx_addr + 1] if idx_addr + 1 < len(lines) else ""
        street = lines[idx_addr + 2] if idx_addr + 2 < len(lines) else ""
        number = lines[idx_addr + 3] if idx_addr + 3 < len(lines) else ""
        zip_code = lines[idx_addr + 4] if idx_addr + 4 < len(lines) else ""
        city = lines[idx_addr + 5] if idx_addr + 5 < len(lines) else ""
        country = lines[idx_addr + 6] if idx_addr + 6 < len(lines) else ""

        data["creditor_name"] = name
        data["creditor_address"] = f"{street} {number}".strip()
        data["creditor_zip"] = zip_code
        data["creditor_city"] = city
        data["creditor_country"] = country

    currency = ""
    currency_idx = None
    for i, l_ in enumerate(lines):
        if l_ in ("CHF", "EUR"):
            currency = l_
            currency_idx = i
            break
    data["currency"] = currency

    amount = ""
    if currency_idx is not None:
        for j in range(currency_idx - 1, max(currency_idx - 8, -1), -1):
            norm = lines[j].replace("'", "").replace(" ", "").replace(",", ".")
            if re.match(r"^\d{1,12}(\.\d{1,2})?$", norm):
                amount = lines[j]
                break
    data["amount"] = amount

    ref = ""
    ref_type = ""
    ref_idx = None
    for i, l_ in enumerate(lines):
        if l_ in ("QRR", "SCOR", "NON"):
            ref_type = l_
            ref_idx = i
            ref = lines[i + 1] if i + 1 < len(lines) else ""
            break
    data["reference"] = ref
    data["reference_type"] = ref_type

    if ref_idx is not None:
        if ref_idx + 2 < len(lines):
            msg = lines[ref_idx + 2]
            if msg != "EPD":
                data["unstructured_message"] = msg

        for j in range(ref_idx + 2, len(lines)):
            if lines[j] == "EPD":
                if j + 1 < len(lines):
                    data["billing_information"] = lines[j + 1]
                if j + 2 < len(lines):
                    data["alt_schemes"] = [
                        x for x in lines[j + 2:] if x and x not in ("AP1", "AP2")
                    ]
                break

    logger.info(
        "SPC fallback parsed → IBAN=%s, Creditor=%s, Amount=%s, Ref=%s (%s)",
        data.get("iban"),
        data.get("creditor_name"),
        data.get("amount"),
        data.get("reference"),
        data.get("reference_type"),
    )
    return data


def _select_best_spc(candidates):
    candidates = [c for c in candidates if is_valid_spc_block(c)]
    if not candidates:
        raise QrInvoiceError("Aucun QR-facture suisse valide trouvé dans le PDF.")

    def score(b):
        u = b.upper()
        s = 0
        if u.startswith("SPC"):
            s += 5
        if "EPD" in u:
            s += 4
        if "CHF" in u or "EUR" in u:
            s += 2
        if "QRR" in u or "SCOR" in u or "NON" in u:
            s += 2
        if _IBAN_CH_RE.search(u):
            s += 4
        s += min(len(u) // 200, 5)
        return s

    best = max(candidates, key=score)
    logger.debug(
        "Best SPC (preview): %s",
        (best[:_MAX_QR_PREVIEW] + '...') if len(best) > _MAX_QR_PREVIEW else best,
    )
    return best


# ---------------------------------------------------------------------------
# Wizard models
# ---------------------------------------------------------------------------

class QrInvoiceStart(ModelView):
    __name__ = 'pl_cust_account.qr_invoice_start'
    qr_file = fields.Binary("Fichier PDF (facture)", required=True)
    qr_filename = fields.Char("Nom du fichier")


class QrInvoiceConfirm(ModelView):
    __name__ = 'pl_cust_account.qr_invoice_confirm'

    qr_filename = fields.Char("Nom du fichier")
    dispose_tva = fields.Boolean("TVA", help="Si coché, la TVA sera retirée.")

    party = fields.Many2One('party.party', "Fournisseur")
    supplier_reference = fields.Char("Réf. fournisseur")
    description = fields.Char("Description", required=True)
    invoice_date = fields.Date("Date facture", required=True)
    date_due = fields.Date("Échéance")
    currency = fields.Many2One('currency.currency', "Devise")
    total_amount = fields.Numeric("Montant TTC", digits=(16, 2))
    journal = fields.Many2One(
        'account.journal', "Journal", required=True,
        domain=[('type', '=', 'expense')],
    )
    iban = fields.Char("IBAN")
    full_text = fields.Text("QR brut")
    pdf_data = fields.Binary("PDF source", states={'invisible': True})

    default_category_account_expense = fields.Many2One(
        'account.account',
        'Default Account Expense',
        required=True
    )
    default_category_account_revenue = fields.Many2One(
        'account.account',
        'Default Account Revenue',
    )
    default_tax_expense = fields.Many2One(
        'account.tax',
        "Tax Expense",
        ondelete='RESTRICT',
        required=False,
    )
    default_tax_revenue = fields.Many2One(
        'account.tax',
        "Tax Revenue",
        ondelete='RESTRICT',
    )

    creditor_name = fields.Char("Bénéficiaire")
    creditor_address = fields.Char("Adresse")
    creditor_zip = fields.Char("NPA")
    creditor_city = fields.Char("Ville")
    creditor_country = fields.Char("Pays")
    qr_amount = fields.Char("Montant QR")
    qr_reference = fields.Char("Référence QR")
    supplier_name = fields.Char("Tiers détecté")


class QrInvoiceWizard(Wizard):
    __name__ = 'pl_cust_account.qr_invoice'

    start = StateView(
        'pl_cust_account.qr_invoice_start',
        'pl_cust_account.qr_invoice_start_view_form',
        [
            Button('Quitter', 'end', 'tryton-cancel'),
            Button('Lire le PDF', 'read_qr', 'tryton-ok', default=True),
        ]
    )

    read_qr = StateTransition()

    confirm = StateView(
        'pl_cust_account.qr_invoice_confirm',
        'pl_cust_account.qr_invoice_confirm_view_form',
        [
            Button('Quitter', 'end', 'tryton-cancel'),
            Button('Retour', 'start', 'tryton-back'),
            Button('Créer la Facture Fournisseur', 'create_invoice', 'tryton-ok', default=True),
        ]
    )

    create_invoice = StateTransition()
    open_invoice = StateAction('account_invoice.act_invoice_in_form')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pdf_filename = None
        self._pdf_bytes = None
        self._parsed = {}

    # ---------------------------
    # Step 1: Read and parse QR
    # ---------------------------
    def transition_read_qr(self):
        logger.info("==> transition_read_qr")
        

        # reset state
        self._parsed = {}
        self._pdf_bytes = None
        self._pdf_filename = None

        blocks = []
        tried_dpi = []

        try:
            # -------------------------------------------------
            # 1) Read binary PDF
            # -------------------------------------------------
            if not self.start.qr_file:
                raise QrInvoiceError("Aucun fichier PDF.")

            filename, data = _decode_binary_input(self.start.qr_file)

            if not data.startswith(b"%PDF-"):
                raise QrInvoiceError("PDF invalide.")
            user_filename = (self.start.qr_filename or '').strip()
            if user_filename:
                filename = user_filename
            elif not filename:
                filename = "qr_invoice.pdf"

            self._pdf_bytes = data
            self._pdf_filename = filename

            # -------------------------------------------------
            # 2) Decode QR (300 dpi -> 600 dpi fallback)
            # -------------------------------------------------
            for dpi in (300, 600):
                logger.info("Tentative lecture QR à %s dpi", dpi)
                try:
                    pages = convert_from_bytes(data, dpi=dpi)
                except Exception as e:
                    logger.error(
                        "Erreur convert_from_bytes(%s dpi): %s",
                        dpi, e, exc_info=True
                    )
                    continue

                tried_dpi.append(dpi)
                logger.info("%d pages converties en %s dpi", len(pages), dpi)

                for page in pages:
                    img = np.array(page.convert("RGB"))[:, :, ::-1]
                    decoded = _low_level_decode(img)
                    if decoded:
                        blocks.extend(decoded)

                if blocks:
                    logger.info("QR détecté avec succès à %s dpi", dpi)
                    break

            # -------------------------------------------------
            # 3) No QR found → manual mode
            # -------------------------------------------------
            if not blocks:
                logger.warning(
                    "Aucun QR détecté (essayé en %s dpi) → passage en mode manuel.",
                    ", ".join(str(d) for d in (tried_dpi or (300, 600))),
                )
                return "confirm"

            # -------------------------------------------------
            # 4) Normalize & debug QR blocks
            # -------------------------------------------------
            blocks = [_clean_qr_text(b) for b in blocks if b]

            logger.info("blocks=%d", len(blocks))
            for i, b in enumerate(blocks[:3]):
                logger.info("block[%d] repr=%r", i, b[:200])
                logger.info(
                    "block[%d] first_lines=%r",
                    i, _split_spc_lines(b)[:6]
                )

            # -------------------------------------------------
            # 5) Filter valid SPC blocks
            # -------------------------------------------------
            spc_blocks = [b for b in blocks if is_valid_spc_block(b)]
            if not spc_blocks:
                logger.warning(
                    "QR détecté mais aucun bloc SPC valide → mode manuel."
                )
                self._parsed = {'full_text': "\n\n".join(blocks)}
                return "confirm"

            # -------------------------------------------------
            # 6) Parse best SPC
            # -------------------------------------------------
            best = _select_best_spc(spc_blocks)
            self._parsed = _parse_spc_dynamic(best)

            logger.info(
                "QR parsé (iban=%s, ref=%s, montant=%s)",
                self._parsed.get("iban"),
                self._parsed.get("reference"),
                self._parsed.get("amount"),
            )

            # -------------------------------------------------
            # 7) IMPORTANT: inject values directly into confirm
            # -------------------------------------------------
            if hasattr(self, 'confirm'):
                raw_amt = (self._parsed.get("amount") or "").strip()
                try:
                    amt = Decimal(
                        raw_amt.replace("'", "").replace(" ", "").replace(",", ".")
                    ) if raw_amt else Decimal("0")
                except Exception:
                    amt = Decimal("0")

                self.confirm.total_amount = amt
                self.confirm.qr_amount = raw_amt
                self.confirm.iban = self._parsed.get("iban") or ""

            return "confirm"

        except QrInvoiceError:
            raise

        except Exception as e:
            logger.error(
                "Erreur inattendue lors de la lecture du QR: %s",
                e, exc_info=True
            )
            raise QrInvoiceError(
                "Erreur lors de la lecture du PDF "
                "(détail technique en log serveur)."
            )


    # ---------------------------
    # Step 2: Create supplier invoice
    # ---------------------------
    def transition_create_invoice(self):
        logger.info("==> transition_create_invoice")
        pool = Pool()

        Invoice = pool.get('account.invoice')
        Company = pool.get('company.company')
        Journal = pool.get('account.journal')
        Address = pool.get('party.address')
        Line = pool.get('account.invoice.line')
        Attachment = pool.get('ir.attachment')
        Party = pool.get('party.party')

        c = self.confirm

        if c.dispose_tva and not c.default_tax_expense:
            raise QrInvoiceError("Vous devez sélectionner une taxe si la TVA est cochée.")
        if not (c.party and c.invoice_date and c.description):
            raise QrInvoiceError("Fournisseur, Date et Description requis.")

        try:
            _ensure_period(pool, c.invoice_date)
        except Exception as e:
            logger.warning("Impossible d'assurer la période comptable: %s", e, exc_info=True)

        # Ensure party is moral + has IBAN if provided + has an address
        party_write = {}
        if 'is_person_moral' in Party._fields and not getattr(c.party, 'is_person_moral', False):
            party_write['is_person_moral'] = True
            if 'firstname' in Party._fields:
                party_write['firstname'] = None
            if 'party_title' in Party._fields:
                party_write['party_title'] = ''
        if 'iban' in Party._fields and c.iban:
            if not (getattr(c.party, 'iban', '') or '').strip():
                party_write['iban'] = c.iban
        if 'party_type' in Party._fields and not getattr(c.party, 'party_type', None):
            party_write['party_type'] = 'f'
        if 'lastname' in Party._fields:
            if not (getattr(c.party, 'lastname', '') or '').strip():
                party_write['lastname'] = (c.creditor_name or c.party.rec_name or 'QR').strip()

        # keep your defaults (accounts/taxes) update
        party_write.update({
            'default_category_account_expense': (c.default_category_account_expense.id if c.default_category_account_expense else None),
            'default_category_account_revenue': (c.default_category_account_revenue.id if c.default_category_account_revenue else None),
            'default_tax_expense': (c.default_tax_expense.id if c.default_tax_expense else None),
            'default_tax_revenue': (c.default_tax_revenue.id if c.default_tax_revenue else None),
        })

        Party.write([c.party], party_write)

        # Ensure address exists (no more hard fail)
        addr = Address.search(
            [('party', '=', c.party.id)],
            order=[('sequence', 'ASC'), ('id', 'ASC')],
            limit=1
        )
        if not addr:
            parsed_for_addr = {
                "creditor_address": c.creditor_address,
                "creditor_zip": c.creditor_zip,
                "creditor_city": c.creditor_city,
                "creditor_country": c.creditor_country,
            }
            invoice_address = _ensure_supplier_address(pool, c.party, parsed_for_addr)
        else:
            invoice_address = addr[0]

        company = None
        if 'company' in getattr(Invoice, '_fields', {}):
            cid = Transaction().context.get('company')
            company = Company(cid) if cid else None

        js = Journal.search([('type', '=', 'expense')], limit=1) or Journal.search([], limit=1)
        journal_fallback = js[0] if js else None

        payable = getattr(c.party, 'account_payable_used', None) or _find_account_by_kind(pool, 'payable')
        if not payable:
            raise QrInvoiceError("Aucun compte fournisseur (kind='payable').")

        inv_vals = {
            'type': 'in',
            'party': c.party.id,
            'invoice_address': invoice_address.id,
            'invoice_date': c.invoice_date,
            'accounting_date': c.invoice_date,
            'description': c.description,
            'reference': (c.supplier_reference or ''),
            'account': payable.id,
        }
        if company and 'company' in Invoice._fields:
            inv_vals['company'] = company.id
        if 'currency' in Invoice._fields and c.currency:
            inv_vals['currency'] = c.currency.id
        journal = c.journal or journal_fallback
        if journal and 'journal' in Invoice._fields:
            inv_vals['journal'] = journal.id
        if 'note' in Invoice._fields and c.full_text:
            inv_vals['note'] = c.full_text
        if 'maturity_date' in Invoice._fields and c.date_due:
            inv_vals['maturity_date'] = c.date_due

        invoice, = Invoice.create([inv_vals])
        logger.info("Facture créée: id=%s", invoice.id)

        # create invoice line
        qty = Decimal('1')
        ttc = c.total_amount or Decimal('0')
        exp = c.default_category_account_expense
        tax = c.default_tax_expense

        if ttc <= 0:
            raise QrInvoiceError("Montant de facture invalide (0).")

        if not exp:
            raise QrInvoiceError("Compte de charge requis (Default Account Expense).")

        taux = Decimal(str(getattr(tax, 'rate', 0) or 0))

        if c.dispose_tva and taux > 0:
            ht = (ttc / (Decimal('1.0') + taux)).quantize(Decimal('0.01'))
            line_vals = {
                'invoice': invoice.id,
                'description': c.description or 'Montant HT',
                'account': exp.id,
                'quantity': qty,
                'unit_price': ht,
                'taxes': [('add', [tax.id])],
            }
        else:
            line_vals = {
                'invoice': invoice.id,
                'description': c.description or 'Montant TTC',
                'account': exp.id,
                'quantity': qty,
                'unit_price': ttc,
                'taxes': [],
            }

        if 'unit' in getattr(Line, '_fields', {}):
            unit = _find_unit(pool)
            if unit:
                line_vals['unit'] = unit.id

        Line.create([line_vals])

        Invoice.update_taxes([invoice])
        invoice.save()

        # attach source PDF if available
        pdf_bytes = None
        raw = getattr(self.confirm, 'pdf_data', None)
        if isinstance(raw, dict) and 'data' in raw:
            raw = raw['data']
        if isinstance(raw, str):
            try:
                pdf_bytes = base64.b64decode(raw)
            except Exception:
                pdf_bytes = None
        elif isinstance(raw, (bytes, bytearray)):
            pdf_bytes = raw
        if not pdf_bytes:
            pdf_bytes = getattr(self, '_pdf_bytes', None)

        if pdf_bytes:
            filename = getattr(self, '_pdf_filename', None)
            if not filename:
                filename = (self.start.qr_filename or '').strip() or 'qr_invoice.pdf'
            resource = ('account.invoice', invoice.id)

            try:
                if 'data' in Attachment._fields:
                    att_vals = {
                        'name': filename,
                        'data': pdf_bytes,
                        'resource': resource,
                    }
                    if 'mimetype' in Attachment._fields:
                        att_vals['mimetype'] = 'application/pdf'
                    Attachment.create([att_vals])
                else:
                    # legacy filestore path
                    File = pool.get('ir.file')
                    fv = {'name': filename}
                    if 'data' in File._fields:
                        fv['data'] = pdf_bytes
                    elif 'file' in File._fields:
                        fv['file'] = pdf_bytes
                    else:
                        raise QrInvoiceError("ir.file sans champ binaire.")
                    if 'mimetype' in File._fields:
                        fv['mimetype'] = 'application/pdf'
                    f, = File.create([fv])
                    Attachment.create([{
                        'name': filename,
                        'file': f.id,
                        'resource': resource,
                    }])
            except (PermissionError, OSError) as exc:
                logger.error(
                    "Erreur d'enregistrement du PDF %r: %s",
                    filename,
                    exc,
                    exc_info=True,
                )
                raise QrInvoiceError(
                    "Impossible d'enregistrer le PDF. "
                    "Vérifiez les droits d'accès au stockage."
                ) from exc
        else:
            logger.info("Aucun PDF à attacher (aucune source disponible).")

        self._invoice = invoice
        return 'open_invoice'

    def do_open_invoice(self, action):
        action['res_id'] = self._invoice.id
        action['views'] = [(None, 'form')]
        action['name'] = 'Facture fournisseur'
        if 'domain' in action:
            action['domain'] = [('id', '=', self._invoice.id)]
        return action, {}

    # ---------------------------
    # Confirm defaults (AUTO CREATE PARTY + ADDRESS HERE)
    # ---------------------------
    def default_confirm(self, fields):
        # If user has already typed something, keep it
        c = getattr(self, 'confirm', None)
        if c and c.description and c.total_amount:
            return {name: getattr(c, name, None) for name in fields}


        pool = Pool()
        Company = pool.get('company.company')
        Journal = pool.get('account.journal')
        Party = pool.get('party.party')

        p = getattr(self, '_parsed', {}) or {}

        # if we only stored full_text, but it is valid SPC, re-parse
        if p and p.get('full_text') and not p.get('iban'):
            try:
                if is_valid_spc_block(p['full_text']):
                    logger.info("Re-parse SPC depuis full_text dans default_confirm")
                    new_p = _parse_spc_dynamic(p['full_text'])
                    new_p['full_text'] = p['full_text']
                    p = self._parsed = new_p
            except Exception:
                logger.exception("Echec re-parse SPC dans default_confirm")

        creditor_name = (p.get("creditor_name") or "").strip()
        iban = (p.get("iban") or "").strip()

        # >>> YOUR REQUEST: auto-create supplier as moral person + create address
        party = None
        if creditor_name or iban:
            party = _ensure_supplier_party(pool, creditor_name, iban)
            _ensure_supplier_address(pool, party, p)

        # amount parsing
        raw_amt = (p.get("amount") or "").strip()

        try:
            amt = Decimal(
                raw_amt.replace("'", "").replace(" ", "").replace(",", ".")
            ) if raw_amt else Decimal("0")
        except Exception:
            amt = Decimal("0")


        # company/currency/journal defaults
        company = Company(Transaction().context.get("company")) if Transaction().context.get("company") else None
        currency = company.currency if company else None

        raw_desc = (
            (p.get("billing_information") or "").strip()
            or (p.get("unstructured_message") or "").strip()
        )

        if not raw_desc:
            raw_desc = f"Facture QR - {creditor_name or 'Fournisseur'}"

        j = Journal.search([("type", "=", "expense")], limit=1) or Journal.search([], limit=1)
        journal = j[0] if j else None

        res = {
            "creditor_name": creditor_name or "",
            "iban": iban,
            "qr_amount": raw_amt,
            "qr_reference": p.get("reference") or "",
            "supplier_name": party.rec_name if party else "",
            "creditor_address": p.get("creditor_address") or "",
            "creditor_zip": p.get("creditor_zip") or "",
            "creditor_city": p.get("creditor_city") or "",
            "creditor_country": p.get("creditor_country") or "",
            "party": party.id if party else None,

            "supplier_reference": p.get("reference") or "",
            "description": raw_desc,
            "invoice_date": date.today(),
            "date_due": None,

            "currency": currency.id if currency else None,
            "total_amount": amt,

            "journal": journal.id if journal else None,
            "full_text": p.get("full_text") or "",
            "pdf_data": getattr(self, "_pdf_bytes", None),
            "qr_filename": (self.start.qr_filename or getattr(self, "_pdf_filename", "") or "").strip(),
        }

        # Copy accounting defaults from party if present
        for field in (
            "default_category_account_expense",
            "default_category_account_revenue",
            "default_tax_expense",
            "default_tax_revenue",
        ):
            if party and field in getattr(Party, "_fields", {}):
                val = getattr(party, field, None)
                res[field] = val.id if val else None
            else:
                res[field] = None

        return res
