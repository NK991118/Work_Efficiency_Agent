import re
import json

from datetime import date

import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect

from .models import User, Rank, Department, Gender, ApprovalLog, Status
from .aws_s3_service import S3Client

def wants_json(request):
    accept = request.headers.get("Accept", "")
    xrw = request.headers.get("X-Requested-With", "")
    return "application/json" in accept or xrw == "XMLHttpRequest"


# 서버측 검증용
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{4,20}$")
PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
)
PHONE_RE = re.compile(r"^010-\d{4}-\d{4}$")
MIN_BIRTH = date(1900, 1, 1)

# 로그아웃
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("uauth:login")

# 로그인
@ensure_csrf_cookie
@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    user = request.user
    if user.is_authenticated and user.status == "approved":
        return redirect("main:home")
    if request.method == "GET":
        return render(request, "uauth/login.html")

    # --- POST ---
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")

    # 필드 유효성
    field_errors = {}
    if not username:
        field_errors["username"] = ["아이디를 입력해주세요."]
    elif len(username) < 3:
        field_errors["username"] = ["아이디는 3자 이상이어야 합니다."]
    if not password:
        field_errors["password"] = ["비밀번호를 입력해주세요."]
    elif len(password) < 4:
        field_errors["password"] = ["비밀번호는 4자 이상이어야 합니다."]

    if field_errors:
        if wants_json(request):
            return JsonResponse(
                {"success": False, "field_errors": field_errors}, status=400
            )
        for _, msgs in field_errors.items():
            messages.error(request, msgs[0])
        return render(request, "uauth/login.html", {"username": username})

    user = authenticate(request, username=username, password=password)

    if user is None:
        # 아이디/비밀번호 오류
        msg = "아이디 또는 비밀번호가 올바르지 않습니다."
        if wants_json(request):
            return JsonResponse({"success": False, "message": msg}, status=400)
        return render(request, "uauth/login.html", {"username": username, "error": msg})

    # 인증 성공
    login(request, user)

    # 최신 승인 상태
    latest_log = ApprovalLog.objects.filter(user=user).order_by("-created_at").first()
    current_status = latest_log.action if latest_log else user.status

    if current_status == Status.PENDING:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "state": "pending",
                    "redirect_url": reverse("uauth:pending"),
                }
            )
        return redirect("uauth:pending")

    if current_status == Status.REJECTED:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "state": "rejected",
                    "redirect_url": reverse("uauth:reject"),
                }
            )
        return redirect("uauth:reject")

    # APPROVED
    if wants_json(request):
        return JsonResponse(
            {"success": True, "state": "approved", "redirect_url": reverse("main:home")}
        )
    return redirect("main:home")


# 회원가입
from django import forms

class SignUpEchoForm(forms.Form):
    userId = forms.CharField(required=True)
    name = forms.CharField(required=True)
    password = forms.CharField(required=True)
    confirmPassword = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    team = forms.CharField(required=False)
    role = forms.CharField(required=True)
    birthDate = forms.DateField(required=True)
    gender = forms.CharField(required=True)
    phoneNumber = forms.CharField(required=True)
    profile_image = forms.ImageField(required=False)


def signup_context(form=None):
    return {
        "form": form or SignUpEchoForm(),
        "departments": Department.choices,
        "ranks": Rank.choices,
        "genders": Gender.choices,
    }


@csrf_protect
@require_http_methods(["GET", "POST"])
def signup_view(request: HttpRequest):
    # GET
    if request.method == "GET":
        return render(request, "uauth/register2.html", signup_context())

    # POST
    form = SignUpEchoForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "uauth/register2.html", signup_context(form))

    # 값 추출
    userId = form.cleaned_data["userId"].strip()
    name = form.cleaned_data["name"].strip()
    password = form.cleaned_data["password"]
    confirm = form.cleaned_data["confirmPassword"]
    email = form.cleaned_data["email"].strip()
    role = form.cleaned_data["role"].strip()
    
    team = (form.cleaned_data.get("team") or "").strip() or None
    if role.lower() == "cto":
        team = None

    birth_dt = form.cleaned_data["birthDate"]
    gender = form.cleaned_data["gender"].strip()
    phone = form.cleaned_data["phoneNumber"].strip()
    
    profile_image = form.cleaned_data.get("profile_image")

    DEFAULT_IMAGE_URL = "https://skn14-codenova-profile.s3.ap-northeast-2.amazonaws.com/profile_image/default2.png"
    image_url = DEFAULT_IMAGE_URL
    
    print("FILES keys:", list(request.FILES.keys()))
    print("file_image:", profile_image, getattr(profile_image, "name", None), getattr(profile_image, "size", None))

    if password != confirm:
        form.add_error("confirmPassword", "비밀번호가 일치하지 않습니다.")
        return render(request, "uauth/register2.html", signup_context(form))
    
    if profile_image:
        if settings.DEBUG:
            save_path = os.path.join("profile_image", profile_image.name)

            stored_name = default_storage.save(save_path, profile_image)
            relative_url = default_storage.url(stored_name)
            image_url = request.build_absolute_uri(relative_url)
        else:
            s3_client = S3Client()
            uploaded_url = s3_client.upload(profile_image)
            if uploaded_url:
                image_url = uploaded_url
            else:
                print("image url 생성 오류, 기본 이미지로 대체")

    # DB 저장
    try:
        with transaction.atomic():
            user = User(
                id=userId,
                email=email,
                name=name,
                department=team,
                rank=role,
                birthday=birth_dt,
                gender=gender,
                phone=phone,
                status=Status.PENDING,
                is_active=True,
                profile_image=image_url,
            )
            user.set_password(password)

            user.save()
            ApprovalLog.objects.get_or_create(
                user=user,
                action=Status.PENDING,
            )

    except IntegrityError:
        form.add_error("userId", "이미 사용 중인 아이디입니다.")
        return render(request, "uauth/register2.html", signup_context(form))

    return redirect("uauth:login")


# JSON API
@csrf_protect
@require_http_methods(["POST"])
def signup_api(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body.decode() or "{}")
    except Exception:
        return JsonResponse({"ok": False, "msg": "Invalid JSON"}, status=400)

    return JsonResponse({"ok": False, "msg": "Not implemented"}, status=400)


# pending페이지
@login_required
def pending_view(request):
    latest_log = (
        ApprovalLog.objects.filter(user=request.user).order_by("-created_at").first()
    )
    current_status = latest_log.action if latest_log else request.user.status

    if current_status == Status.APPROVED:
        return redirect("main:home")
    if current_status == Status.REJECTED:
        return redirect("uauth:reject")

    return render(request, "uauth/pending.html")


@login_required
def reject_view(request):
    latest_log = (
        ApprovalLog.objects.filter(user=request.user).order_by("-created_at").first()
    )
    current_status = latest_log.action if latest_log else request.user.status

    if current_status == Status.APPROVED:
        return redirect("main:home")
    if current_status == Status.PENDING:
        return redirect("uauth:pending")

    approval_log = (
        ApprovalLog.objects.filter(user=request.user, action__iexact="rejected")
        .order_by("-created_at")
        .first()
    )

    if not approval_log:
        approval_log = (
            ApprovalLog.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )

    return render(request, "uauth/reject.html", {"approval_log": approval_log})
