from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


# User profile for login activity tracking
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('viewer', 'Viewer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    first_login = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    is_active_user = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)

    can_manage_students = models.BooleanField(default=False)
    can_manage_payments = models.BooleanField(default=False)
    can_manage_expenses = models.BooleanField(default=False)
    can_manage_purchases = models.BooleanField(default=False)
    can_manage_settlements = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_export_collection_excel = models.BooleanField(default=False)
    can_export_expense_excel = models.BooleanField(default=False)
    can_export_purchase_excel = models.BooleanField(default=False)
    can_export_payment_excel = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    def has_permission(self, permission_name):
        if self.role == 'admin':
            return True
        if self.role == 'staff':
            return bool(getattr(self, permission_name, False))
        return False


# Mess Settings
class MessSetting(models.Model):
    total_students = models.PositiveIntegerField(default=0, help_text="Total number of students in the mess")

    def __str__(self):
        return f"Total Students: {self.total_students}"

    class Meta:
        verbose_name = "Mess Setting"
        verbose_name_plural = "Mess Settings"


# Accounting Period
class AccountingPeriod(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="e.g. August 2026")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


# Period-wise default fee
class PeriodDefaultFee(models.Model):
    period = models.OneToOneField(AccountingPeriod, on_delete=models.CASCADE, related_name='default_fee')
    default_fee_per_student = models.DecimalField(max_digits=12, decimal_places=2, help_text="Default fee per active student for this period")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period__start_date']

    def __str__(self):
        return f"{self.period.name} | Default Fee: ₹{self.default_fee_per_student}"


# Student
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    hostel_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    student_name = models.CharField(max_length=150, blank=True, default='', help_text="Proper display name with spaces (e.g. Aman Jaiswal). Used in payment receipt emails. Duplicate names allowed.")
    room_no = models.CharField(max_length=10, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, help_text="Optional Gmail address for payment receipts")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        full_name = self.student_name or self.user.get_full_name() or self.user.username
        hostel = self.hostel_id or "No ID"
        return f"{hostel} - {full_name}"

    def get_display_name(self):
        return self.student_name or self.user.get_full_name() or self.user.username


# Student period-wise due/account
class StudentPeriodAccount(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='period_accounts')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name='student_accounts')
    total_to_collect = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total amount to collect from this student for this period")
    manual_remaining = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="If set, overrides the auto-calculated remaining amount")
    is_manual_remaining = models.BooleanField(default=False, help_text="Whether remaining amount is manually set")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'period')
        ordering = ['period__start_date', 'student__hostel_id']

    def __str__(self):
        return f"{self.student} | {self.period.name} | Collect: ₹{self.total_to_collect}"

    def get_display_remaining(self):
        if self.is_manual_remaining and self.manual_remaining is not None:
            return self.manual_remaining
        return self.total_to_collect - self.get_total_paid()

    def get_total_paid(self):
        from django.db.models import Sum
        total = Payment.objects.filter(
            student=self.student,
            period=self.period,
            status='PAID'
        ).aggregate(total=Sum('amount'))['total']
        return total or 0

    def get_remaining_type(self):
        if self.is_manual_remaining and self.manual_remaining is not None:
            return "Manual"
        return "Auto"


# Payment
class Payment(models.Model):
    METHOD_CHOICES = [
        ('UPI', 'UPI'),
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Bank', 'Bank'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'PENDING'),
        ('PAID', 'PAID'),
    ]
    PAYMENT_MODE_CHOICES = [
        ('default_fee', 'Use Default Fee'),
        ('custom_full', 'Custom / Full Paid Amount'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    month = models.DateField(help_text="Use the first day of the month")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_entries')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    adjustment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # +discount / -extra
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='UPI')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    txn_id = models.CharField(max_length=100, blank=True)
    payment_mode = models.CharField(
        max_length=20, choices=PAYMENT_MODE_CHOICES, default='custom_full',
        help_text="Use Default Fee = apply this period's configured default fee for future calculations. Custom Full Paid = this payment amount IS the total full due."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} | {self.month:%b %Y} | ₹{self.amount} ({self.status})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than 0.'})


# Supplier
class Supplier(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.name


# Stock items
class StockItem(models.Model):
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)  # kg, L, pcs
    min_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name


# Purchase (bills)
class Purchase(models.Model):
    UNIT_CHOICES = [
        ('Gram', 'Gram'),
        ('Kg', 'Kg'),
        ('Litre', 'Litre'),
        ('Packet', 'Packet'),
        ('Piece', 'Piece'),
        ('Other', 'Other'),
    ]
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name='purchases')
    bill_no = models.CharField(max_length=50)
    bill_date = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_entries')
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='purchases')
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='Other', help_text="Unit for this purchase entry")
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bill_file = models.FileField(upload_to='bills/', blank=True)

    class Meta:
        ordering = ['-bill_date']

    def __str__(self):
        return f"{self.supplier} #{self.bill_no} | {self.bill_date:%d-%b-%Y} | ₹{self.amount}"


# Issue to kitchen
class IssueToKitchen(models.Model):
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='issues')
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    issued_to = models.CharField(max_length=50, default='Kitchen')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.item.name} → {self.issued_to} | {self.qty} {self.item.unit}"


# Labour
class Labour(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50)  # cook/helper/cleaner
    monthly_wage = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.role})"


# Labour payment
class LabourPayment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'PENDING'),
        ('PAID', 'PAID'),
    ]

    labour = models.ForeignKey(Labour, on_delete=models.CASCADE, related_name='payments')
    month = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='labour_payment_entries')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        ordering = ['-month']

    def __str__(self):
        return f"{self.labour.name} | {self.month:%b %Y} | ₹{self.amount} ({self.status})"


# Other expenses
class OtherExpense(models.Model):
    category = models.CharField(max_length=50)  # gas/electricity/maintenance
    month = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='other_expense_entries')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-month']

    def __str__(self):
        return f"{self.category} | {self.month:%b %Y} | ₹{self.amount}"


# Monthly settlement (surplus/deficit)
class MonthlySettlement(models.Model):
    month = models.DateField(unique=True)
    accounting_period = models.ForeignKey(AccountingPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='settlements')
    total_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    surplus_deficit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_student_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    finalized = models.BooleanField(default=False)

    class Meta:
        ordering = ['-month']

    def __str__(self):
        return f"{self.month:%b %Y} | Surplus: ₹{self.surplus_deficit} | Finalized: {self.finalized}"


class EmailOTP(models.Model):
    PURPOSE_CHOICES = [
        ('signup', 'Signup'),
        ('forgot_password', 'Forgot Password'),
    ]
    email = models.CharField(max_length=254)
    otp_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} - {self.purpose} - verified={self.is_verified}"

    @staticmethod
    def hash_otp(otp):
        return make_password(otp)

    def verify_otp(self, otp):
        return check_password(otp, self.otp_hash)