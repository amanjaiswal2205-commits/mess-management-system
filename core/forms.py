from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Student, Payment, StudentPeriodAccount, AccountingPeriod, MessSetting, PeriodDefaultFee, UserProfile, Purchase


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=True, label="Full Name")
    username = forms.CharField(max_length=150, required=True, label="Username")
    email = forms.EmailField(required=True, label="Email Address")
    password1 = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, request):
        full_name = self.cleaned_data['full_name'].strip()
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''

        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            first_name=first_name,
            last_name=last_name,
        )
        return user


class StudentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=False, label="Last Name")

    class Meta:
        model = Student
        fields = ['hostel_id', 'room_no', 'phone', 'is_active']
        labels = {
            'hostel_id': 'Hostel ID / Roll Number (Optional)',
            'room_no': 'Room Number',
            'phone': 'Phone Number',
            'is_active': 'Active',
        }

    def __init__(self, *args, **kwargs):
        self.user_instance = kwargs.pop('user_instance', None)
        super().__init__(*args, **kwargs)
        if self.user_instance:
            self.fields['first_name'].initial = self.user_instance.first_name
            self.fields['last_name'].initial = self.user_instance.last_name

    def clean_hostel_id(self):
        hostel_id = self.cleaned_data.get('hostel_id')
        if hostel_id:
            qs = Student.objects.filter(hostel_id=hostel_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A student with this Hostel ID already exists.")
            if User.objects.filter(username=hostel_id).exists():
                raise forms.ValidationError("This Hostel ID is already taken. Please choose a different one.")
        return hostel_id

    def save(self, commit=True):
        student = super().save(commit=False)
        if self.user_instance:
            user = self.user_instance
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
        else:
            user = User()
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            student.is_active = True

        if student.hostel_id:
            user.username = student.hostel_id
        else:
            base_username = f"student_{User.objects.count() + 1}"
            user.username = base_username

        if commit:
            user.save()
            student.user = user
            student.save()
        return student


class StudentSearchForm(forms.Form):
    query = forms.CharField(max_length=100, required=False, label="Search")


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['student', 'period', 'amount', 'month', 'method', 'txn_id', 'status']
        widgets = {
            'month': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'student': 'Student',
            'period': 'Accounting Period',
            'amount': 'Payment Amount (₹)',
            'month': 'Payment Date',
            'method': 'Payment Mode',
            'txn_id': 'Transaction / Reference ID',
            'status': 'Status',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].min_value = 0.01
        self.fields['status'].choices = [('PAID', 'PAID')]
        self.fields['status'].initial = 'PAID'


class StudentPeriodAccountForm(forms.ModelForm):
    is_manual_remaining = forms.BooleanField(
        required=False,
        label="Set Remaining Manually",
        help_text="Enable to override the auto-calculated remaining amount"
    )

    class Meta:
        model = StudentPeriodAccount
        fields = ['student', 'period', 'total_to_collect', 'is_manual_remaining', 'manual_remaining']
        labels = {
            'student': 'Student',
            'period': 'Accounting Period',
            'total_to_collect': 'Monthly Fee / Amount to Collect (₹)',
            'manual_remaining': 'Manual Remaining Amount (₹)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['total_to_collect'].min_value = 0
        self.fields['manual_remaining'].required = False
        if self.instance and self.instance.pk:
            self.fields['is_manual_remaining'].initial = self.instance.is_manual_remaining


class PeriodFilterForm(forms.Form):
    period = forms.ModelChoiceField(
        queryset=AccountingPeriod.objects.all().order_by('-start_date'),
        required=True,
        label="Accounting Period",
        empty_label="Select Period",
    )


class MessSettingForm(forms.ModelForm):
    class Meta:
        model = MessSetting
        fields = ['total_students']
        labels = {
            'total_students': 'Total Students',
        }


class PeriodDefaultFeeForm(forms.ModelForm):
    class Meta:
        model = PeriodDefaultFee
        fields = ['period', 'default_fee_per_student']
        labels = {
            'period': 'Accounting Period',
            'default_fee_per_student': 'Default Fee Per Active Student (₹)',
        }

    def clean_default_fee_per_student(self):
        fee = self.cleaned_data['default_fee_per_student']
        if fee is not None and fee <= 0:
            raise forms.ValidationError("Default fee must be greater than 0.")
        return fee


class StaffPermissionForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'can_manage_students',
            'can_manage_payments',
            'can_manage_expenses',
            'can_manage_purchases',
            'can_manage_settlements',
            'can_view_reports',
            'can_export_collection_excel',
            'can_export_expense_excel',
            'can_export_purchase_excel',
            'can_export_payment_excel',
        ]
        labels = {
            'can_manage_students': 'Manage Students',
            'can_manage_payments': 'Manage Payments',
            'can_manage_expenses': 'Manage Expenses',
            'can_manage_purchases': 'Manage Purchases',
            'can_manage_settlements': 'Manage Settlements',
            'can_view_reports': 'View Reports',
            'can_export_collection_excel': 'Export Collection Excel',
            'can_export_expense_excel': 'Export Expense Excel',
            'can_export_purchase_excel': 'Export Purchase Excel',
            'can_export_payment_excel': 'Export Payment Excel',
        }
        widgets = {
            'can_manage_students': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_payments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_expenses': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_purchases': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_settlements': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_view_reports': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_export_collection_excel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_export_expense_excel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_export_purchase_excel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_export_payment_excel': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ['supplier', 'bill_no', 'bill_date', 'period', 'item', 'qty', 'unit', 'rate', 'amount', 'bill_file']
        labels = {
            'supplier': 'Supplier',
            'bill_no': 'Bill No.',
            'bill_date': 'Bill Date',
            'period': 'Accounting Period',
            'item': 'Item/Product',
            'qty': 'Quantity',
            'unit': 'Unit',
            'rate': 'Unit Price (₹)',
            'amount': 'Total Amount (₹)',
            'bill_file': 'Bill File',
        }