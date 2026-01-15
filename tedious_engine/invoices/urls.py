from django.urls import path

from invoices import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
