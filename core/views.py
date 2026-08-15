import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'messmgt.settings')
import django
django.setup()

from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from core.models import (
    UserProfile, MessSetting, AccountingPeriod, PeriodDefaultFee,
    Student, StudentPeriodAccount, Payment, Supplier, StockItem,
    Purchase, IssueToKitchen, Labour, LabourPayment, OtherExpense,
    MonthlySettlement,
)
from core.decorators import (
    admin_required, viewer_or_admin_required, staff_or_admin_required,
    staff_permission_required, user_has_permission,
)
from core.forms import StudentForm, PaymentForm, PeriodDefaultFeeForm, StudentSearchForm, PurchaseForm, SignupForm
from django.contrib import messages
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.helpers import complete_social_login

PER_PAGE = 25

UserModel = get_user_model()


# Pagination helpers
def _build_query_string(request, exclude=None):
    exclude = exclude or []
    params = []
    for key in request.GET:
        if key in exclude:
            continue
        values = request.GET.getlist(key)
        for value in values:
            params.append(f"{key}={value}")
    if params:
        return "&".join(params) + "&"
    return ""


def _page_range_list(page_obj):
    paginator = page_obj.paginator
    current = page_obj.number
    total = paginator.num_pages
    if total <= 7:
        return list(range(1, total + 1))
    pages = []
    if current <= 3:
        pages.extend(range(1, 6))
        pages.append(None)
        pages.append(total)
    elif current >= total - 2:
        pages.append(1)
        pages.append(None)
        pages.extend(range(total - 4, total + 1))
    else:
        pages.append(1)
        pages.append(None)
        pages.extend(range(current - 1, current + 2))
        pages.append(None)
        pages.append(total)
    return pages


def _paginate(request, queryset, per_page=None, page_param='page'):
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    if per_page is None:
        per_page = PER_PAGE
    paginator = Paginator(queryset, per_page)
    page = request.GET.get(page_param) or request.GET.get('p') or 1
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    page_range_list = _page_range_list(page_obj)
    query_string = _build_query_string(request, exclude=[page_param, 'p'])
    return {
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'page_range_list': page_range_list,
        'query_string': query_string,
        'page_param': page_param,
    }


# Auth / misc
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save(request)
            messages.success(request, 'Account created successfully! Please login to continue.')
            return redirect('account_login')
    else:
        form = SignupForm()
    return render(request, 'core/signup.html', {'form': form})


def google_login(request):
    adapter = GoogleOAuth2Adapter(request)
    return complete_social_login(request, adapter)


# Home & Dashboard
def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')


@login_required
@viewer_or_admin_required
def dashboard(request):
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from collections import defaultdict
    import json

    profile = getattr(request.user, 'profile', None)

    total_fee = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0

    total_expense = 0
    total_expense += Purchase.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_expense += LabourPayment.objects.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or 0
    total_expense += OtherExpense.objects.aggregate(total=Sum('amount'))['total'] or 0

    surplus_deficit = total_fee - total_expense

    fee_qs = Payment.objects.annotate(
        month_trunc=TruncMonth('month')
    ).values('month_trunc').annotate(total=Sum('amount')).order_by('month_trunc')

    purchase_expense = Purchase.objects.annotate(
        month_trunc=TruncMonth('bill_date')
    ).values('month_trunc').annotate(total=Sum('amount'))

    labour_expense = LabourPayment.objects.filter(status='PAID').annotate(
        month_trunc=TruncMonth('month')
    ).values('month_trunc').annotate(total=Sum('amount'))

    other_expense = OtherExpense.objects.annotate(
        month_trunc=TruncMonth('month')
    ).values('month_trunc').annotate(total=Sum('amount'))

    all_months = set()
    for entry in fee_qs:
        all_months.add(entry['month_trunc'])
    for entry in purchase_expense:
        all_months.add(entry['month_trunc'])
    for entry in labour_expense:
        all_months.add(entry['month_trunc'])
    for entry in other_expense:
        all_months.add(entry['month_trunc'])

    fee_lookup = {entry['month_trunc']: float(entry['total'] or 0) for entry in fee_qs}
    expense_lookup = defaultdict(float)
    for entry in purchase_expense:
        expense_lookup[entry['month_trunc']] += float(entry['total'] or 0)
    for entry in labour_expense:
        expense_lookup[entry['month_trunc']] += float(entry['total'] or 0)
    for entry in other_expense:
        expense_lookup[entry['month_trunc']] += float(entry['total'] or 0)

    sorted_months = sorted(all_months)
    months = [m.strftime('%b %Y') for m in sorted_months]
    fees = [fee_lookup.get(m, 0) for m in sorted_months]
    expenses = [expense_lookup.get(m, 0) for m in sorted_months]

    recent_purchases = Purchase.objects.select_related('supplier', 'item').all().order_by('-bill_date')[:5]

    context = {
        'user': request.user,
        'profile': profile,
        'total_fee': total_fee,
        'total_expense': total_expense,
        'surplus_deficit': surplus_deficit,
        'months': json.dumps(months),
        'fees': json.dumps(fees),
        'expenses': json.dumps(expenses),
        'recent_purchases': recent_purchases,
    }
    return render(request, 'core/dashboard.html', context)


# Students
@login_required
@viewer_or_admin_required
def student_list(request):
    qs = Student.objects.all().order_by('hostel_id')
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(hostel_id__icontains=search) |
            Q(room_no__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    ctx = _paginate(request, qs, PER_PAGE)
    page_obj = ctx['page_obj']
    ctx['students'] = page_obj.object_list
    ctx['search_form'] = StudentSearchForm(initial={'query': search})
    ctx['search'] = search
    ctx['total_students'] = qs.count()
    ctx['named_students'] = qs.filter(user__first_name__gt='').count()
    ctx['unnamed_students'] = ctx['total_students'] - ctx['named_students']
    return render(request, 'core/student_list.html', ctx)


@login_required
@staff_permission_required('can_export_collection_excel')
def students_export_excel(request):
    return HttpResponse("export students", content_type='text/plain')


@login_required
@staff_permission_required('can_manage_students')
def student_add(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Student added.')
                return redirect('student_list')
            except Exception as e:
                messages.error(request, f'Could not save student: {e}')
    else:
        form = StudentForm()
    return render(request, 'core/student_form.html', {'form': form})


@login_required
@staff_permission_required('can_manage_students')
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student, user_instance=student.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student updated.')
            return redirect('student_list')
    else:
        form = StudentForm(instance=student, user_instance=student.user)
    return render(request, 'core/student_form.html', {'form': form, 'student': student})


@login_required
@staff_permission_required('can_manage_students')
def student_toggle_active(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.is_active = not student.is_active
    student.save()
    return redirect('student_list')


@login_required
@admin_required
def mess_setting(request):
    setting = MessSetting.objects.first()
    form = MessSettingForm(instance=setting)
    if request.method == 'POST':
        form = MessSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mess settings updated.')
            return redirect('student_list')
    return render(request, 'core/mess_setting_form.html', {'form': form, 'setting': setting})


# Period Default Fee
@login_required
@admin_required
def period_default_fee_set(request, period_id):
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    obj, created = PeriodDefaultFee.objects.get_or_create(period=period)
    if request.method == 'POST':
        form = PeriodDefaultFeeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Default fee saved.')
            return redirect('dashboard')
    else:
        form = PeriodDefaultFeeForm(instance=obj)
    return render(request, 'core/period_default_fee_form.html', {'form': form, 'period': period})


@login_required
@admin_required
def period_default_fee_apply_unset(request, period_id):
    return redirect('dashboard')


@login_required
@admin_required
def period_default_fee_apply_all(request, period_id):
    return redirect('dashboard')


# Payments
@login_required
@viewer_or_admin_required
def payments_list(request):
    qs = Payment.objects.all().order_by('-created_at')
    ctx = _paginate(request, qs, PER_PAGE)
    ctx['payments'] = ctx['page_obj'].object_list
    return render(request, 'core/payments_list.html', ctx)


@login_required
@staff_permission_required('can_export_payment_excel')
def payments_export_excel(request):
    return HttpResponse("export payments", content_type='text/plain')


@login_required
@viewer_or_admin_required
def payment_summary(request):
    from django.db.models import Sum, F, DecimalField
    from django.db.models.functions import Coalesce

    period_form = PeriodFilterForm(request.GET)
    selected_period = None
    summary = []

    if period_form.is_valid():
        selected_period = period_form.cleaned_data.get('period')

    if selected_period:
        accounts = StudentPeriodAccount.objects.filter(period=selected_period).select_related('student__user')
        for account in accounts:
            total_paid = Payment.objects.filter(
                student=account.student, period=selected_period, status='PAID'
            ).aggregate(total=Sum('amount'))['total'] or 0
            total_paid = float(total_paid) if total_paid else 0
            remaining = account.get_display_remaining()
            remaining = float(remaining) if str(remaining).replace('-', '').replace('.', '').isdigit() else 0
            is_pending = total_paid < float(account.total_to_collect or 0)
            status_class = 'bg-success' if not is_pending else 'bg-warning text-dark'
            status_text = 'Paid' if not is_pending else 'Due'
            summary.append({
                'student': account.student,
                'total_to_collect': account.total_to_collect,
                'total_paid': total_paid,
                'display_remaining': remaining,
                'remaining_type': account.get_remaining_type(),
                'status_class': status_class,
                'status': status_text,
            })

    return render(request, 'core/payment_summary.html', {
        'period_form': period_form,
        'selected_period': selected_period,
        'summary': summary,
    })


@login_required
@staff_permission_required('can_manage_payments')
def payment_add(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Payment recorded.')
                return redirect('payments_list')
            except Exception as e:
                messages.error(request, f'Could not save payment: {e}')
    else:
        form = PaymentForm()
    return render(request, 'core/payment_form.html', {'form': form})


@login_required
@staff_permission_required('can_export_payment_excel')
def payments_summary_export_excel(request):
    return HttpResponse("summary export", content_type='text/plain')


@login_required
@staff_permission_required('can_manage_payments')
def payment_due_edit(request, student_id, period_id):
    account = get_object_or_404(StudentPeriodAccount, student_id=student_id, period_id=period_id)
    form = StudentPeriodAccountForm(request.POST or None, instance=account)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Monthly fee updated.')
        return redirect('payment_summary')
    return render(request, 'core/payment_due_form.html', {'form': form, 'account': account, 'student': account.student, 'period': account.period})


@login_required
@viewer_or_admin_required
def payment_history(request, student_id, period_id):
    account = get_object_or_404(StudentPeriodAccount, student_id=student_id, period_id=period_id)
    qs = Payment.objects.filter(student=account.student, period=account.period).order_by('-created_at')
    ctx = _paginate(request, qs, PER_PAGE)
    ctx['account'] = account
    return render(request, 'core/payment_history.html', ctx)


def student_search_api(request):
    q = request.GET.get('q', '')
    students = Student.objects.filter(
        Q(hostel_id__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
    )[:10]
    data = [
        {'id': s.id, 'hostel_id': s.hostel_id, 'name': s.user.get_full_name() or s.user.username}
        for s in students
    ]
    return JsonResponse({'results': data})


# Purchases
@login_required
@viewer_or_admin_required
def purchases_list(request):
    qs = Purchase.objects.all().order_by('-bill_date')
    ctx = _paginate(request, qs, PER_PAGE)
    ctx['purchases'] = ctx['page_obj'].object_list
    return render(request, 'core/purchases_list.html', ctx)


@login_required
@staff_permission_required('can_manage_purchases')
def purchase_add(request):
    if request.method == 'POST':
        form = PurchaseForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Purchase recorded.')
                return redirect('purchases_list')
            except Exception as e:
                messages.error(request, f'Could not save purchase: {e}')
    else:
        form = PurchaseForm()
    return render(request, 'core/purchase_form.html', {'form': form})


@login_required
@staff_permission_required('can_manage_purchases')
def purchase_edit(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        form = PurchaseForm(request.POST, request.FILES, instance=purchase)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase updated.')
            return redirect('purchases_list')
    else:
        form = PurchaseForm(instance=purchase)
    return render(request, 'core/purchase_form.html', {'form': form, 'purchase': purchase})


@login_required
@staff_permission_required('can_export_purchase_excel')
def purchases_export_excel(request):
    return HttpResponse("export purchases", content_type='text/plain')


# Expenses
@login_required
@viewer_or_admin_required
def expenses_list(request):
    labour_qs = LabourPayment.objects.select_related('labour').all().order_by('-month')
    other_qs = OtherExpense.objects.all().order_by('-month')

    labour_ctx = _paginate(request, labour_qs, PER_PAGE, page_param='labour_page')
    other_ctx = _paginate(request, other_qs, PER_PAGE, page_param='other_page')

    ctx = {}
    ctx['labour_expenses'] = labour_ctx['page_obj'].object_list
    ctx['labour_page_obj'] = labour_ctx['page_obj']
    ctx['labour_paginator'] = labour_ctx['page_obj'].paginator
    ctx['labour_is_paginated'] = labour_ctx['is_paginated']
    ctx['labour_query_string'] = labour_ctx['query_string']
    ctx['labour_page_range'] = labour_ctx['page_range_list']

    ctx['other_expenses'] = other_ctx['page_obj'].object_list
    ctx['other_page_obj'] = other_ctx['page_obj']
    ctx['other_paginator'] = other_ctx['page_obj'].paginator
    ctx['other_is_paginated'] = other_ctx['is_paginated']
    ctx['other_query_string'] = other_ctx['query_string']
    ctx['other_page_range'] = other_ctx['page_range_list']

    return render(request, 'core/expenses_list.html', ctx)


@login_required
@staff_permission_required('can_export_expense_excel')
def expenses_export_excel(request):
    return HttpResponse("export expenses", content_type='text/plain')


# Settlements
@login_required
@viewer_or_admin_required
def settlement_list(request):
    qs = MonthlySettlement.objects.all().order_by('-month')
    ctx = _paginate(request, qs, PER_PAGE)
    ctx['settlements'] = ctx['page_obj'].object_list
    ctx['periods'] = AccountingPeriod.objects.order_by('start_date')
    return render(request, 'core/settlement_list.html', ctx)


@login_required
@staff_permission_required('can_manage_settlements')
def settlements_export_excel(request):
    return HttpResponse("export settlements", content_type='text/plain')


@login_required
@admin_required
def auto_settlement(request, year, month, closed_days):
    period = get_object_or_404(AccountingPeriod, start_date__year=year, start_date__month=month)
    # Simplified settlement logic
    students = Student.objects.filter(is_active=True)
    total_fee = 0
    total_expense = 0
    total_paid = 0
    for student in students:
        account, created = StudentPeriodAccount.objects.get_or_create(
            student=student, period=period,
            defaults={'total_to_collect': 0}
        )
        payments = Payment.objects.filter(student=student, period=period, status='PAID')
        paid = payments.aggregate(total=Sum('amount'))['total'] or 0
        total_paid += paid

    purchases = Purchase.objects.filter(period=period)
    total_expense = purchases.aggregate(total=Sum('amount'))['total'] or 0

    labour_payments = LabourPayment.objects.filter(period=period, status='PAID')
    total_expense += labour_payments.aggregate(total=Sum('amount'))['total'] or 0

    other_expenses = OtherExpense.objects.filter(period=period)
    total_expense += other_expenses.aggregate(total=Sum('amount'))['total'] or 0

    per_student = StudentPeriodAccount.objects.filter(period=period).aggregate(
        total=Sum('total_to_collect'))['total'] or 0
    total_fee = per_student

    surplus_deficit = total_fee - total_expense
    num_students = students.count()
    per_student_adjustment = surplus_deficit / num_students if num_students else 0

    settlement, created = MonthlySettlement.objects.get_or_create(
        month=period.start_date.replace(day=1),
        defaults={'accounting_period': period}
    )
    settlement.total_fee = total_fee
    settlement.total_expense = total_expense
    settlement.surplus_deficit = surplus_deficit
    settlement.per_student_adjustment = per_student_adjustment
    settlement.opening_balance = 0
    settlement.closing_balance = surplus_deficit
    settlement.finalized = True
    settlement.save()

    messages.success(request, f'Settlement done for {period.name}.')
    return redirect('settlement_list')


@login_required
@admin_required
def period_settlement(request, period_id):
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    # Reuse auto_settlement logic with 0 closed_days placeholder
    return auto_settlement(request, period.start_date.year, period.start_date.month, 0)


# Reports
@login_required
@staff_permission_required('can_view_reports')
def purchases_report(request):
    qs = Purchase.objects.all().order_by('-bill_date')
    ctx = _paginate(request, qs, PER_PAGE)
    return render(request, 'core/purchases_report.html', ctx)


@login_required
@staff_permission_required('can_view_reports')
def master_report(request):
    return render(request, 'core/master_report.html', {})


# User Activity (Admin Only)
@admin_required
def user_activity(request):
    profiles = UserProfile.objects.select_related('user').order_by('-updated_at')
    ctx = _paginate(request, profiles, PER_PAGE)
    ctx['profiles'] = ctx['page_obj']
    ctx.pop('page_obj', None)
    return render(request, 'core/user_activity.html', ctx)


# User Management (Admin Only)
@admin_required
def user_manage(request):
    profiles = UserProfile.objects.select_related('user').all()
    return render(request, 'core/user_manage.html', {'profiles': profiles})


@admin_required
def user_change_role(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    if request.method == 'POST':
        role = request.POST.get('role')
        if role in ['admin', 'staff', 'viewer']:
            profile.role = role
            profile.save()
            messages.success(request, f'Role changed to {role}.')
    return redirect('user_manage')


@admin_required
def user_toggle_account(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.is_active_user = not profile.is_active_user
    profile.save()
    messages.success(request, 'Account status toggled.')
    return redirect('user_manage')


@admin_required
def user_permissions_edit(request, user_id):
    profile = get_object_or_404(UserProfile, user_id=user_id)
    if request.method == 'POST':
        for field in [
            'can_manage_students', 'can_manage_payments', 'can_manage_expenses',
            'can_manage_purchases', 'can_manage_settlements', 'can_view_reports',
            'can_export_collection_excel', 'can_export_expense_excel',
            'can_export_purchase_excel', 'can_export_payment_excel',
        ]:
            setattr(profile, field, request.POST.get(field) == 'on')
        profile.save()
        messages.success(request, 'Permissions updated.')
    return render(request, 'core/user_permissions_edit.html', {'profile': profile})
