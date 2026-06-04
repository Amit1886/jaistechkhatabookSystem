from django.urls import path

from khataapp.core_engine import api_views


app_name = "central_engine_api"


urlpatterns = [
    path("central-engine/summary/", api_views.api_summary, name="summary"),
    path("central-engine/rewards/", api_views.api_rewards, name="rewards"),
    path("central-engine/tasks/complete/", api_views.api_complete_task, name="task_complete"),
]

