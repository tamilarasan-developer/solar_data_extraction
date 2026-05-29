from django.db import models


class FeederDataRaw(models.Model):

    station = models.CharField(max_length=255)
    round_off_time = models.DateTimeField()
    ssid = models.CharField(max_length=50)
    voltage = models.CharField(max_length=50)

    feeder_name = models.CharField(max_length=255)

    meter_no = models.CharField(
        max_length=50,
    )

    mw = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0
    )

    mvar = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0
    )

    mw_sign = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    mvar_sign = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    export_mw = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0
    )

    import_mw = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0
    )

    net_mw = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0
    )

    direction = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    communication = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    rtc_time = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    class Meta:
        db_table = "FeederDataRaw"

    def __str__(self):
        return self.feeder_name




class MainFeederData(models.Model):

    station = models.CharField(max_length=255)

    feeder_name = models.CharField(max_length=255)

    round_off_time = models.DateTimeField()

    avg_export_mw = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=0
    )

    avg_net_mw = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=0
    )

    sample_count = models.IntegerField(
        default=0
    )

    class Meta:
        db_table = "main_feeder_data"

        unique_together = (
            "station",
            "feeder_name",
            "round_off_time"
        )

    def __str__(self):
        return f"{self.station} - {self.feeder_name}"