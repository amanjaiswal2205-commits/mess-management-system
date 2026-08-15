from django.contrib import admin
from .models import (
    AccountingPeriod, Student, Payment, Supplier, StockItem, Purchase,
    IssueToKitchen, Labour, LabourPayment, OtherExpense, MonthlySettlement,
    StudentPeriodAccount, MessSetting, PeriodDefaultFee, UserProfile
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'role', 'is_active_user', 'first_login', 'last_login', 'login_count')
    list_filter = ('role', 'is_active_user')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    ordering = ('-created_at',)
    list_editable = ('role', 'is_active_user')
    readonly_fields = ('first_login', 'last_login', 'login_count', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'role', 'is_active_user')
        }),
        ('Staff Permissions', {
            'fields': (
                'can_manage_students', 'can_manage_payments',
                'can_manage_expenses', 'can_manage_purchases',
                'can_manage_settlements', 'can_view_reports',
                'can_export_collection_excel', 'can_export_expense_excel',
                'can_export_purchase_excel', 'can_export_payment_excel',
            ),
            'classes': ('collapse',),
        }),
        ('Activity', {
            'fields': ('first_login', 'last_login', 'login_count', 'created_at', 'updated_at'),
        }),
    )


@admin.register(MessSetting)
class MessSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'total_students')
    list_editable = ('total_students',)


@admin.register(PeriodDefaultFee)
class PeriodDefaultFeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'period', 'default_fee_per_student', 'updated_at')
    list_filter = ('period',)
    search_fields = ('period__name',)
    ordering = ('-period__start_date',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'start_date', 'end_date', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)
    ordering = ('-start_date',)
    list_per_page = 25


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'hostel_id', 'room_no', 'phone', 'is_active', 'user')
    search_fields = ('hostel_id', 'room_no', 'phone',
                     'user__username', 'user__first_name', 'user__last_name')
    ordering = ('hostel_id',)
    list_per_page = 25
    list_editable = ('is_active',)


@admin.register(StudentPeriodAccount)
class StudentPeriodAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'period', 'total_to_collect', 'updated_at')
    list_filter = ('period',)
    search_fields = ('student__hostel_id', 'student__user__first_name', 'student__user__last_name', 'period__name')
    ordering = ('-period__start_date', 'student__hostel_id')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'month', 'period', 'amount', 'adjustment_amount',
                    'method', 'status', 'txn_id', 'created_at')
    list_filter = ('status', 'method', 'month', 'period')
    search_fields = ('student__hostel_id', 'student__user__username', 'txn_id')
    autocomplete_fields = ('student',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    list_editable = ('status',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone')
    search_fields = ('name', 'phone')
    list_per_page = 25


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'unit', 'min_level')
    search_fields = ('name',)
    list_per_page = 25


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'bill_no', 'bill_date', 'period',
                    'item', 'qty', 'rate', 'amount')
    list_filter = ('bill_date', 'supplier', 'period')
    search_fields = ('bill_no', 'supplier__name', 'item__name')
    ordering = ('-bill_date',)
    date_hierarchy = 'bill_date'
    list_per_page = 25


@admin.register(IssueToKitchen)
class IssueToKitchenAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'qty', 'date', 'issued_to')
    list_filter = ('date',)
    search_fields = ('item__name', 'issued_to')
    date_hierarchy = 'date'
    list_per_page = 25


@admin.register(Labour)
class LabourAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'role', 'monthly_wage')
    search_fields = ('name', 'role')
    list_per_page = 25


@admin.register(LabourPayment)
class LabourPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'labour', 'month', 'period', 'amount', 'status')
    list_filter = ('status', 'month', 'period')
    search_fields = ('labour__name',)
    ordering = ('-month',)
    date_hierarchy = 'month'
    list_editable = ('status',)
    list_per_page = 25


@admin.register(OtherExpense)
class OtherExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'month', 'period', 'amount', 'note')
    list_filter = ('month', 'category', 'period')
    search_fields = ('category', 'note')
    ordering = ('-month',)
    date_hierarchy = 'month'
    list_per_page = 25


@admin.register(MonthlySettlement)
class MonthlySettlementAdmin(admin.ModelAdmin):
    list_display = ('id', 'month', 'total_fee', 'total_expense',
                    'surplus_deficit', 'per_student_adjustment', 'finalized')
    list_filter = ('finalized', 'month')
    ordering = ('-month',)
    date_hierarchy = 'month'
    list_per_page = 25