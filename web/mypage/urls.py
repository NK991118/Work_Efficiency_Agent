from django.urls import path
from . import views

app_name = "mypage"

urlpatterns = [
    path("", views.mypage, name="mypage"),
    path("card_detail/<int:card_id>/", views.card_detail, name="card_detail"),
    path("mypage/api_key_delete/<int:key_id>/", views.api_key_delete, name="api_key_delete"),
    path("mypage/mypage_edit", views.mypage_edit, name="mypage_edit"),
    path("check_api_key_name/", views.check_api_key_name, name="check_api_key_name"),
    path("api-key/create/", views.create_api_key, name="create_api_key"),
]
