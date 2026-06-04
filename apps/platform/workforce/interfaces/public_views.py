from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.platform.workforce.models import PublicWorkforceApplication


@require_POST
def public_workforce_apply(request):
    full_name = (request.POST.get("full_name") or "").strip()
    mobile = (request.POST.get("mobile") or "").strip()
    applicant_type = (request.POST.get("applicant_type") or "employee").strip()

    valid_types = {choice[0] for choice in PublicWorkforceApplication.ApplicantType.choices}
    if applicant_type not in valid_types:
        applicant_type = "employee"

    if not full_name or not mobile:
        return JsonResponse(
            {"status": "error", "message": "Name and mobile number are required."},
            status=400,
        )

    application = PublicWorkforceApplication.objects.create(
        applicant_type=applicant_type,
        full_name=full_name,
        mobile=mobile,
        email=(request.POST.get("email") or "").strip(),
        city=(request.POST.get("city") or "").strip(),
        role_interest=(request.POST.get("role_interest") or "").strip(),
        experience_years=request.POST.get("experience_years") or 0,
        skills=(request.POST.get("skills") or "").strip(),
        resume=request.FILES.get("resume"),
        interview_slot=(request.POST.get("interview_slot") or "").strip(),
        portfolio_url=(request.POST.get("portfolio_url") or "").strip(),
        referral_code=(request.POST.get("referral_code") or "").strip(),
        source="landing",
        metadata={
            "ip": (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip(),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
        },
    )

    return JsonResponse(
        {
            "status": "success",
            "message": "Application received. Our hiring team will contact you for screening/interview.",
            "application_id": str(application.id),
        },
        status=201,
    )
