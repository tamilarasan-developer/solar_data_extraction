from django.db import models


class FeederDataRaw(models.Model):

    station = models.CharField(max_length=255)
    round_off_time = models.CharField(max_length=100)

    # NEW COLUMN
    script_run_time = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

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
        round_off_str = self.round_off_time if self.round_off_time else 'N/A'
        script_run_str = self.script_run_time if self.script_run_time else 'N/A'
        return f"{self.feeder_name} (Round-off: {round_off_str}, Run: {script_run_str})"


class MainFeederData(models.Model):

    station = models.CharField(max_length=255)

    feeder_name = models.CharField(max_length=255)

    round_off_time = models.CharField(max_length=100)

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

    class Meta:
        db_table = "main_feeder_data"

        unique_together = (
            "station",
            "feeder_name",
            "round_off_time"
        )

    def __str__(self):
        round_off_str = self.round_off_time if self.round_off_time else 'N/A'
        return f"{self.station} - {self.feeder_name} (Round-off: {round_off_str})"