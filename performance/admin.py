from django.contrib import admin

from performance.models import LeaderboardEntry, Reward, Target


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "period", "target_value", "achieved_value", "start_date", "end_date")
    list_filter = ("period",)


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "period", "user", "score", "rank", "computed_at")


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "points", "awarded_at")
