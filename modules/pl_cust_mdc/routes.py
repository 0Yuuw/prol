# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import requests
from datetime import date, datetime
import time
import json
import logging
from werkzeug.exceptions import abort
from werkzeug.wrappers import Response
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.wsgi import app
from trytond.protocols.wrappers import with_pool, with_transaction, user_application
from trytond.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
import smtplib

from email.encoders import encode_base64
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.mime.text import MIMEText

from email.utils import COMMASPACE, formatdate
import mimetypes

book_application = user_application("book")
# config.get('pl_cust', 'token')

import random

def generer_numero_reference(longueur):
    caracteres = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    numero_reference = "".join(random.choice(caracteres) for i in range(longueur))
    return numero_reference


def my_format_day(date):
    if not date:
        return "-"

    corresp = {
        1: "Lundi",
        2: "Mardi",
        3: "Mercredi",
        4: "Jeudi",
        5: "Vendredi",
        6: "Samedi",
        7: "Dimanche",
    }

    corresp2 = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre",
    }

    return "{:15s} {:4d} {:11s} {}".format(
        corresp[date.isoweekday()],
        date.day,
        corresp2[date.month],
        date.strftime("%Y"),
    )


@app.route("/<database_name>/book/get_pub_date", methods=["GET"])
@with_pool
@with_transaction()
@book_application
def get_pub_date(request, pool):           
    logger.info("Request arrived at /{}/book/get_pub_date".format(request.view_args['database_name']))

    days = pool.get("pl_cust_mdc.day_pub")
    Date = pool.get("ir.date")
    days_list = days.search(
        [("date", ">=", Date.today()), ("dtype", "=", "p")], order=[("date", "ASC")]
    )
    logger.info(f"Days list contains {len(days_list)} records")
    # J-M-A
    res = []

    for days in days_list:
        logger.info(f"Processing date: {days.date}")
        color = "bg-green-200"
        if days.tot_morning:
            color = "bg-red-200"
        if days.tot_morning < days.nb_max:
            res.append(
                {
                    "text": "{} matin ({} places à partir de 09h00)".format(
                        my_format_day(days.date), days.nb_max - days.tot_morning
                    ),
                    "nb": days.nb_max - days.tot_morning,
                    "value": "{}/m".format(days.id),
                    "nb_max": days.nb_max,
                }
            )
        color = "bg-green-200"
        if days.tot_afternoon:
            color = "bg-red-200"
        if days.tot_afternoon < days.nb_max:
            res.append(
                {
                    "text": "{} après-midi ({} places à partir de 14h00)".format(
                        my_format_day(days.date), days.nb_max - days.tot_afternoon
                    ),
                    "nb": days.nb_max - days.tot_afternoon,
                    "value": "{}/a".format(days.id),
                    "nb_max": days.nb_max,
                }
            )

    logger.info(f"Resulting response contains {len(res)} records")
    return Response(json.dumps(res), mimetype="application/json")


@app.route("/<database_name>/book/get_inst_date", methods=["GET"])
@with_pool
@with_transaction()
@book_application
def get_inst_date(request, pool):
    days = pool.get("pl_cust_mdc.day_inst")
    Date = pool.get("ir.date")
    days_list = days.search(
        [("date", ">", Date.today()), ("dtype", "=", "i")], order=[("date", "ASC")]
    )
    # J-M-A
    res = []
    for days in days_list:

        if days.tot_inst_m < days.nb_inst_max and days.tot_inst_a < days.nb_inst_max:
            res.append(
                {
                    "text": "{}".format(my_format_day(days.date)),
                    "nb": 0,
                    "value": "{}/m".format(days.id),
                }
            )
        elif days.tot_inst_m < days.nb_inst_max:
            res.append(
                {
                    "text": "{} (uniquement le matin)".format(my_format_day(days.date)),
                    "nb": 1,
                    "value": "{}/m".format(days.id),
                }
            )
        elif days.tot_inst_a < days.nb_inst_max:
            res.append(
                {
                    "text": "{} (uniquement l'après-midi)".format(
                        my_format_day(days.date)
                    ),
                    "nb": 1,
                    "value": "{}/m".format(days.id),
                }
            )

        if False and days.tot_morning < days.nb_max:
            res.append(
                {
                    "text": "{} ({} places à 09h00)".format(
                        my_format_day(days.date), days.nb_max - days.tot_morning
                    ),
                    "value": "{}/m".format(days.id),
                }
            )
        if False and days.tot_afternoon < days.nb_max:
            res.append(
                {
                    "text": "{} ({} places à 14h00)".format(
                        my_format_day(days.date), days.nb_max - days.tot_afternoon
                    ),
                    "value": "{}/a".format(days.id),
                }
            )

    return res
    # return Response('Plus valide', 404)


def send_mail_info(book, name="-"):
    if book.email_sent:
        print(f"Mail already send for: {book.id}")
        return {"status": "success", "message": "Email already sent no action taken"}

    TO = book.email
    if not TO:
        print("Email not provided, using fallback")
        TO = "nguyen@prolibre.com"

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = "noreply@mdc-reg.ch"
        msg["To"] = TO
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = "Votre billet"

        msg.attach(
            MIMEText(
                f"""Bonjour,

Veuillez trouvez ci-joint votre billet pour la maison de la créativité. 

Au plaisir de vous voir,
                """,
                "plain",
            )
        )

        Ticket = Pool().get("pl_cust_mdc.mdc_reportpub", type="report")
        ext, content, _, title = Ticket.execute([book.id], {})
        name = f"{title}.{ext}"
        if isinstance(content, str):
            content = content.encode("utf-8")

        mimetype, _ = mimetypes.guess_type(name)
        if mimetype:
            attachment = MIMENonMultipart(*mimetype.split("/"))
            attachment.set_payload(content)
            encode_base64(attachment)
        else:
            attachment = MIMEApplication(content)
        attachment.add_header(
            "Content-Disposition", "attachment", filename=("utf-8", "", name)
        )
        msg.attach(attachment)

        pl_user = "noreply@mdc-reg.ch"
        pl_passwd = "591P-dq$HCnO-"
        server = smtplib.SMTP("mail.infomaniak.com", 587)
        server.starttls()
        server.login(pl_user, pl_passwd)
        server.sendmail("noreply@mdc-reg.ch", [TO], msg.as_string())
        server.quit()

        print("Mail sent successfully.")

        book.email_sent = True
        book.save()

        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        print(f"Error sending email: {e}")
        return {"status": "error", "message": str(e)}



# def gift_send_mail_info(book, name="-"):
#     if book.gift_email_sent:
#         print(f"Mail already send for: {book.id}")
#         return {"status": "success", "message": "Email already sent no action taken"}

#     TO = book.email
#     if not TO:
#         print("Email not provided, using fallback.")
#         TO = "nguyen@prolibre.com"

#     try:
#         msg = MIMEMultipart("mixed")
#         msg["From"] = "noreply@mdc-reg.ch"
#         msg["To"] = TO
#         msg["Date"] = formatdate(localtime=True)
#         msg["Subject"] = "Votre Bon Cadeau"

#         msg.attach(
#             MIMEText(
#                 f"""Bonjour,

# Veuillez trouvez ci-joint votre bon cadeau pour la maison de la créativité, pensez à venir le retirer.

# Au plaisir de vous voir,
#                 """,
#                 "plain",
#             )
#         )

#         Ticket = Pool().get("pl_cust_mdc.mdc_reportgift", type="report")
#         ext, content, _, title = Ticket.execute([book.id], {})
#         name = f"{title}.{ext}"
#         if isinstance(content, str):
#             content = content.encode("utf-8")

#         mimetype, _ = mimetypes.guess_type(name)
#         if mimetype:
#             attachment = MIMENonMultipart(*mimetype.split("/"))
#             attachment.set_payload(content)
#             encode_base64(attachment)
#         else:
#             attachment = MIMEApplication(content)
#         attachment.add_header(
#             "Content-Disposition", "attachment", filename=("utf-8", "", name)
#         )
#         msg.attach(attachment)

#         pl_user = "noreply@mdc-reg.ch"
#         pl_passwd = "591P-dq$HCnO-"
#         server = smtplib.SMTP("mail.infomaniak.com", 587)
#         server.starttls()
#         server.login(pl_user, pl_passwd)
#         server.sendmail("noreply@mdc-reg.ch", [TO], msg.as_string())
#         server.quit()

#         print("Gift email sent successfully.")

#         book.gift_email_sent = True
#         book.save()

#         return {"status": "success", "message": "Gift email sent successfully"}
#     except Exception as e:
#         print(f"Error sending gift email: {e}")
#         return {"status": "error", "message": str(e)}



def get_datatrans_id(
    amo, ref, merchant_id, password, url, successUrl, cancelUrl, errorUrl
):
    data = {
        "currency": "CHF",
        "refno": ref,
        "amount": amo,
        "redirect": {
            "successUrl": "{}".format(successUrl),
            "cancelUrl": "{}".format(cancelUrl),
            "errorUrl": "{}".format(errorUrl),
        },
    }
    response = requests.post(url, json=data, auth=(merchant_id, password))

    if response.ok:
        return response.json().get("transactionId")
    # else:
    #     response.raise_for_status()


@app.route("/<database_name>/book/savepubbook", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def savepubbook(request, pool):
    Book = pool.get("pl_cust_mdc.booking_pub")
    Day = pool.get("pl_cust_mdc.day_pub")
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)
    if request.method in {"POST"}:

        data = request.parsed_data.copy()
        days_id = Day.search([("id", "=", data["item"]["dates_id"].split("/")[0])])
        if days_id:
            days_id = days_id[0]

        d = Day(days_id)

        print(data["item"]["association"])

        tot_nb = (
            int(data["item"]["tarifAdulte"])
            + int(data["item"]["bonCadeau"])
            + int(data["item"]["association"])
            + int(data["item"]["tarif02"])
            + int(data["item"]["tarif34"])
            + int(data["item"]["tarif56"])
            + int(data["item"]["tarif78"])
        )
        if data["item"]["dates_id"].split("/")[1] == "m":
            if d.tot_morning + tot_nb > d.nb_max:
                return Response("NbrMax", 404)
        else:
            if d.tot_afternoon + tot_nb > d.nb_max:
                return Response("NbrMax", 404)

        amo = 0
        if data["item"]["sp4"]:
            amo += tot_nb * 4
        elif data["item"]["sp5"]:
            amo += tot_nb * 5
        elif data["item"]["sp6"]:
            amo += tot_nb * 6
        else:
            amo += int(data["item"]["tarifAdulte"]) * conf_val.price_adult
            amo += int(data["item"]["association"]) * conf_val.price_asso
            amo += int(data["item"]["tarif02"]) * conf_val.price_02
            amo += int(data["item"]["tarif34"]) * conf_val.price_34
            amo += int(data["item"]["tarif56"]) * conf_val.price_56
            amo += int(data["item"]["tarif78"]) * conf_val.price_78

        if amo:
            amo *= 100

        refno = generer_numero_reference(12)

        print(conf_val.datatrans_successUrl)
        if amo:
            TransactionID = get_datatrans_id(
                amo,
                refno,
                conf_val.merchant_id,
                conf_val.merchant_password,
                conf_val.datatrans_url,
                conf_val.datatrans_successUrl,
                conf_val.datatrans_cancelUrl,
                conf_val.datatrans_errorUrl,
            )
        else:
            TransactionID = refno

        reg = Book.create(
            [
                {  # 'day': data['item']['availableDates'],
                    "day": days_id,
                    "npa": data["item"]["npa"],
                    "nb_adult": data["item"]["tarifAdulte"],
                    "nb_asso": data["item"]["association"],
                    "nb_02": data["item"]["tarif02"],
                    "nb_34": data["item"]["tarif34"],
                    "nb_56": data["item"]["tarif56"],
                    "nb_78": data["item"]["tarif78"],
                    "nb_gift": data["item"]["bonCadeau"],
                    "sp4": data["item"]["sp4"],
                    "sp5": data["item"]["sp5"],
                    "sp6": data["item"]["sp6"],
                    "mad": data["item"]["dates_id"].split("/")[1],
                    "name_asso": data["item"]["associationNom"],
                    "datatrans_id": TransactionID,
                    "refno": refno,
                    "email": data["item"]["email"],
                    "state": amo and "draft" or "payed",
                }
            ]
        )

        return Response(
            json.dumps({"TransactionID": TransactionID, "refno": refno}),
            mimetype="application/json",
        )

    return Response(
        json.dumps({"error": "Reqête invalide"}),
        status=404,
        mimetype="application/json",
    )





@app.route("/<database_name>/book/saveinstbook", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def saveinstbook(request, pool):
    Book = pool.get("pl_cust_mdc.booking_inst")
    Day = pool.get("pl_cust_mdc.day_inst")
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)

    if request.method in {"POST"}:
        try:
            data = request.parsed_data.copy()

            if "item" not in data or "dates_id" not in data["item"]:
                return Response(
                    json.dumps({"error": "'dates_id' is required in 'item'"}),
                    status=400,
                    mimetype="application/json",
                )

            dates_id_raw = data["item"]["dates_id"]

            try:
                days_id_value = dates_id_raw.split("/")[0]
            except AttributeError as e:
                return Response(
                    json.dumps({"error": "'dates_id' must be a string in the format 'id/...'" }),
                    status=400,
                    mimetype="application/json",
                )

            days_id = Day.search([("id", "=", days_id_value)])

            if not days_id:
                return Response(
                    json.dumps({"error": "Erreur dans la date"}),
                    status=404,
                    mimetype="application/json",
                )

            days_id = days_id[0]
            d = Day(days_id)

            reg = Book.create(
                [
                    {
                        "day": days_id,
                        "nb_child": data["item"]["nombreEnfants"],
                        "nb_adult": data["item"]["nombreAdultes"],
                        "inst_comment": data["item"]["commentaires"],
                        "child_year": data["item"]["ageEnfants"],
                        "inst_rep": data["item"]["repondant"],
                        "inst_tel": data["item"]["telephoneContact"],
                        "inst_type": data["item"]["typeStructure"],
                        "inst_email": data["item"]["email"],
                        "inst_prov": data["item"]["provenance"],
                        "inst_address": data["item"]["adresse"],
                        "inst_zip": data["item"]["zipcode"],
                        "inst_name": data["item"]["nomStructure"],
                        "inst_activity": data["item"]["activity"],
                        "mad": data["item"]["periodeJournee"],
                        "sieste": data["item"]["sieste"] and True or False,
                        "piqueNique": data["item"]["piqueNique"] and True or False,
                        "state": "draft",
                    }
                ]
            )

            return Response(
                json.dumps(
                    {
                        "ok": """Votre préinscription pour le {} a bien été prise en compte. Vous recevrez une confirmation par mail dans quelques jours.  
            Au plaisir de vous voir""".format(
                            my_format_day(d.date)
                        )
                    }
                ),
                mimetype="application/json",
            )
        except Exception as e:
            return Response(
                json.dumps({"error": "Internal Server Error", "details": str(e)}),
                status=500,
                mimetype="application/json",
            )

    return Response(
        json.dumps({"error": "Requête invalide"}),
        status=404,
        mimetype="application/json",
    )




@app.route("/<database_name>/book/validate", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def validate(request, pool):
    Book = pool.get("pl_cust_mdc.booking_pub")
    Conf = pool.get("pl_cust_mdc.configuration")

    conf_val = Conf(1)
    print("On est ici et on check")
    if request.method in {"POST"}:
        data = request.parsed_data.copy()
        b = Book.search([("datatrans_id", "=", data["item"]["TransactionID"])])
        if b:
            b = b[0]
            b.state = "payed"
            b.save()
            send_mail_info(b)

            return Response("ok")
        else:
            return Response(None, 404)

    return Response(None, 404)


@app.route("/<database_name>/book/checkticket", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def validate_refno(request, pool):
    Book = pool.get("pl_cust_mdc.booking_pub")
    Conf = pool.get("pl_cust_mdc.configuration")
    Date = pool.get("ir.date")
    conf_val = Conf(1)

    print("on est ici!")
    if request.method in {"POST"}:
        data = request.parsed_data.copy()

        b = Book.search([("refno", "=", data["item"]["refno"])])

    if b:
        b = b[0]
        if b.day.date != Date.today():
            return Response(
                json.dumps({"error": "Requête invalide",
                            "tot_live_morning": b.day.tot_live_morning,
                            "tot_live_afternoon": b.day.tot_live_afternoon,}),
                status=404,
                mimetype="application/json",
            )
        elif b.used:
            return Response(
                json.dumps({"error": "Ticket déjà utilisé",
                            "tot_live_morning": b.day.tot_live_morning,
                            "tot_live_afternoon": b.day.tot_live_afternoon,}),
                status=404,
                mimetype="application/json",
            )
        b.used = True
        b.save()

        return Response(
            json.dumps(
                {
                    "tot_live_morning": b.day.tot_live_morning,
                    "tot_live_afternoon": b.day.tot_live_afternoon,
                    "nb_adult": b.nb_adult,
                    "nb_asso": b.nb_asso,
                    "nb_02": b.nb_02,
                    "nb_34": b.nb_34,
                    "nb_56": b.nb_56,
                    "nb_78": b.nb_78,
                    "nb_gift": b.nb_gift,
                }
            ),
            mimetype="application/json",
        )

    else:
        return Response(
            json.dumps({"error": "Ticket introuvable"}),
            status=404,
            mimetype="application/json",
        )

    return Response(
        json.dumps({"error": "Requête invalide"}),
        status=404,
        mimetype="application/json",
    )


@app.route("/<database_name>/book/getticket", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def get_ticket(request, pool):
    Book = pool.get("pl_cust_mdc.booking_pub")

    if request.method == "POST":
        data = request.parsed_data.copy()
        b = Book.search([("datatrans_id", "=", data["item"]["TransactionID"])])

        if b:
            book = b[0]
            pool = Pool()
            Ticket = Pool().get("pl_cust_mdc.mdc_reportpub", type="report")
            ext, content, _, title = Ticket.execute([book.id], {})
            if isinstance(content, str):
                content = content.encode("utf-8")

            return Response(content)
        else:
            return Response(None, 404)

    return Response(None, 404)


@app.route("/<database_name>/book/buy-voucher", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def buyvoucher(request, pool):
    Book = pool.get("pl_cust_mdc.gift_voucher")
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)
    if request.method in {"POST"}:

        data = request.parsed_data.copy()

        amo = 0
        amo += int(data["item"]["tarif2"]) * conf_val.price_2
        amo += int(data["item"]["tarif4"]) * conf_val.price_4
        amo += int(data["item"]["tarif10"]) * conf_val.price_10

        if amo:
            amo = amo * 100

        refno = generer_numero_reference(12)

        print(conf_val.datatrans_successUrl)
        if amo:
            TransactionID = get_datatrans_id(
                amo,
                refno,
                conf_val.merchant_id,
                conf_val.merchant_password,
                conf_val.datatrans_url,
                conf_val.datatrans_giftSuccessUrl,
                conf_val.datatrans_cancelUrl,
                conf_val.datatrans_errorUrl,
            )
        else:
            TransactionID = refno

        print(data["item"]["tarif2"])
        print(data["item"]["tarif4"])
        print(data["item"]["tarif10"])

        reg = Book.create(
            [
                {
                    "lastname": data["item"]["nom"],
                    "firstname": data["item"]["prenom"],
                    "npa": data["item"]["npa"],
                    "nb_2": data["item"]["tarif2"],
                    "nb_4": data["item"]["tarif4"],
                    "nb_10": data["item"]["tarif10"],
                    "email": data["item"]["email"],
                    "datatrans_id": TransactionID,
                    "refno": refno,
                    "state": amo and "draft" or "payed",
                }
            ]
        )

        return Response(
            json.dumps({"TransactionID": TransactionID, "refno": refno}),
            mimetype="application/json",
        )

    return Response(
        json.dumps({"error": "Reqête invalide"}),
        status=404,
        mimetype="application/json",
    )


@app.route("/<database_name>/book/validatevoucher", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def validate_voucher(request, pool):
    Book = pool.get("pl_cust_mdc.gift_voucher")
    Conf = pool.get("pl_cust_mdc.configuration")

    conf_val = Conf(1)
    print("On est ici et on check les gifts")
    if request.method in {"POST"}:
        data = request.parsed_data.copy()
        b = Book.search([("datatrans_id", "=", data["item"]["TransactionID"])])
        if b:
            b = b[0]
            b.state = "payed"
            b.save()
            gift_send_mail_info(b)

            return Response("ok")
        else:
            return Response(None, 404)

    return Response(None, 404)


@app.route("/<database_name>/book/getgiftticket", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def get_ticket(request, pool):
    Book = pool.get("pl_cust_mdc.gift_voucher")

    if request.method == "POST":
        data = request.parsed_data.copy()

        b = Book.search([("datatrans_id", "=", data["item"]["TransactionID"])])

        if b:
            book = b[0]
            pool = Pool()
            Ticket = Pool().get("pl_cust_mdc.mdc_reportgift", type="report")
            ext, content, _, title = Ticket.execute([book.id], {})
            if isinstance(content, str):
                content = content.encode("utf-8")

            return Response(content)
        else:
            return Response(None, 404)

    else:
        return Response(None, 404)


@app.route("/<database_name>/book/checkgift", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def validate_gift(request, pool):
    Book = pool.get("pl_cust_mdc.gift_voucher")
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)

    print("on est ici!")
    if request.method in {"POST"}:
        data = request.parsed_data.copy()

        b = Book.search([("refno", "=", data["item"]["refno"])])

    if b:
        b = b[0]
        if b.used:
            return Response(
                json.dumps({"error": "Bon déjà utilisé"}),
                status=404,
                mimetype="application/json",
            )
        b.used = True
        b.save()

        return Response(
            json.dumps(
                {
                    "nb_2": b.nb_2,
                    "nb_4": b.nb_4,
                    "nb_10": b.nb_10,
                }
            ),
            mimetype="application/json",
        )

    else:
        return Response(
            json.dumps({"error": "Bon introuvable"}),
            status=404,
            mimetype="application/json",
        )

    return Response(
        json.dumps({"error": "Requête invalide"}),
        status=404,
        mimetype="application/json",
    )


@app.route("/<database_name>/book/checkticket", methods=["POST"])
@with_pool
@with_transaction()
@book_application
def validate_gift_refno(request, pool):
    Book = pool.get("pl_cust_mdc.gift_voucher")
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)

    print("on est ici!")
    if request.method in {"POST"}:
        data = request.parsed_data.copy()
        b = Book.search([("refno", "=", data["item"]["refno"])])

        if b:
            b = b[0]
            if not b.used:
                b.used = True
                b.save()

                return Response(
                    json.dumps(
                        {
                            "nb_2": b.nb_2,
                            "nb_4": b.nb_4,
                            "nb_10": b.nb_10,
                        }
                    ),
                    mimetype="application/json",
                )
            else:
                return Response(
                    json.dumps({"error": "Ticket déjà utilisé"}),
                    status=404,
                    mimetype="application/json",
                )
        else:
            return Response(
                json.dumps({"error": "Ticket introuvable"}),
                status=404,
                mimetype="application/json",
            )

    return Response(
        json.dumps({"error": "Requête invalide"}),
        status=404,
        mimetype="application/json",
    )

@app.route("/<database_name>/book/gift_price", methods=["GET"])
@with_pool
@with_transaction()
def gift_price(request, pool):
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)

    return Response(
        json.dumps(
            {
                "price_2": conf_val.price_2,
                "price_4": conf_val.price_4,
                "price_10": conf_val.price_10,
            }
        ),
        mimetype="application/json",
    )

@app.route("/<database_name>/book/pub_price", methods=["GET"])
@with_pool
@with_transaction()
def pub_price(request, pool):
    Conf = pool.get("pl_cust_mdc.configuration")
    conf_val = Conf(1)

    return Response(
        json.dumps(
            {
                "nb_adult": conf_val.price_adult,
                "nb_02": conf_val.price_02,
                "nb_34": conf_val.price_34,
                "nb_56": conf_val.price_56,
                "nb_78": conf_val.price_78,
                "nb_gift": conf_val.price_gift,
                "nb_asso": conf_val.price_asso,
            }
        ),
        mimetype="application/json",
    )
