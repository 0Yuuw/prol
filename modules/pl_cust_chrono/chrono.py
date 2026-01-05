from trytond.model import ModelSQL, ModelView, fields, DeactivableMixin
from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError, UserWarning
from trytond.pyson import Eval,If
from datetime import timedelta,datetime


class ChronoWarning(UserWarning):
    pass


__all__ = ["Chrono", "ChronoLine"]


class ChronoLine(ModelSQL, ModelView):
    "ChronoLine"

    __name__ = "pl_cust_chrono.chronoline"

    chrono = fields.Many2One("pl_cust_chrono.chrono", "Chrono", required=True)
    start = fields.DateTime("Start")
    stop = fields.DateTime("Stop")
    duration = fields.Function(fields.TimeDelta("Duration"), "on_change_with_duration")

    @fields.depends("start", "stop")
    def on_change_with_duration(self, name=None):
        if self.start and self.stop:
            return self.stop - self.start
        else:
            return timedelta()


class Chrono(ModelSQL, ModelView):
    "Chrono"

    __name__ = "pl_cust_chrono.chrono"

    chronolines = fields.One2Many("pl_cust_chrono.chronoline", "chrono", "Chrono Lines")
    description = fields.Char("Description")
    date = fields.Date("Date")

    duration = fields.Function(fields.TimeDelta("Duration"), "on_change_with_duration")
    is_running = fields.Function(
        fields.Boolean("Is running"), "on_change_with_is_running"
    )

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree', 'visual', If(Eval('is_running'), 'success', '')),
        ]


    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls._buttons.update(
            {
                "chrono_start": {
                    'invisible': Eval('is_running'),
                },
                 "chrono_stop": {
                    'invisible': ~Eval('is_running'),
                },
            }
        )

    # mise à jour des infos via un bouton
    @classmethod
    @ModelView.button
    def chrono_start(cls, chronos):
        Date_ = Pool().get("ir.date")

        CHRONO = Pool().get("pl_cust_chrono.chrono")
        CHRONOLINE = Pool().get("pl_cust_chrono.chronoline")

        chrono_run = CHRONO.search(
            [("date", "=", Date_.today())]
        )

        for cr in chrono_run:
            for crl in cr.chronolines:
                if crl.start and not crl.stop:
                    crl.stop = datetime.now()
                    crl.save()
                    break

        for c in chronos[0:]:
            new_cl = CHRONOLINE.create(
                [
                    {
                        "chrono": c.id,
                        "start": datetime.now(),
                    }
                ]
            )
            new_cl[0].save()

        return 'reload'

    #####################

    # mise à jour des infos via un bouton
    @classmethod
    @ModelView.button
    def chrono_stop(cls, chronos):
        Date_ = Pool().get("ir.date")

        CHRONO = Pool().get("pl_cust_chrono.chrono")
        CHRONOLINE = Pool().get("pl_cust_chrono.chronoline")

        chrono_run = CHRONO.search(
            [("date", "=", Date_.today())]
        )

        for cr in chrono_run:
            for crl in cr.chronolines:
                if crl.start and not crl.stop:
                    crl.stop = datetime.now()
                    crl.save()
                    break

        return 'reload'

    #####################

    @staticmethod
    def default_date():
        Date_ = Pool().get("ir.date")
        return Date_.today()

    @fields.depends("chronolines")
    def on_change_with_duration(self, name=None):
        tot = timedelta()
        for l in self.chronolines:
            if l.duration:
                tot += l.duration

        return tot

    @fields.depends("chronolines")
    def on_change_with_is_running(self, name=None):
        for l in self.chronolines:
            if l.start and not l.stop:
                return True

        return False
