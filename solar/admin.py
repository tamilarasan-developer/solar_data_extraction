from django.contrib import admin
from .models import FeederDataRaw, MainFeederData

@admin.register(FeederDataRaw)
class FeederDataRawAdmin(admin.ModelAdmin):
    list_display = (
        'station',
        'feeder_name',
        'round_off_time',
        'script_run_time',
        'net_mw',
        'export_mw'
    )


@admin.register(MainFeederData)
class MainFeederDataAdmin(admin.ModelAdmin):
    list_display = (
        'station',
        'feeder_name',
        'round_off_time',
        'avg_export_mw',
        'avg_net_mw'
    )
