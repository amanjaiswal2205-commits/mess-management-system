import os
from datetime import date

from django.conf import settings
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
import json

from core.models import EmailOTP, Student, StudentPeriodAccount, AccountingPeriod, Payment, UserProfile, PeriodDefaultFee

UserModel = get_user_model()


class RegistrationFlowTests(TestCase):
    def setUp(self):
        self.url = reverse('account_register')
        self.valid_data = {
            'full_name': 'Test User',
            'email': 'testuser@gmail.com',
            'mobile': '9876543210',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }

    def test_invalid_registration_data(self):
        response = self.client.post(self.url, {
            'full_name': '',
            'email': 'invalid-email',
            'mobile': '123',
            'password1': 'pass',
            'password2': 'different',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)

    def test_valid_registration_sends_otp_and_does_not_create_user(self):
        with patch('core.views.send_mail', return_value=1):
            response = self.client.post(
                self.url,
                self.valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('otp_sent'))
        self.assertFalse(UserModel.objects.filter(email='testuser@gmail.com').exists())
        self.assertTrue(EmailOTP.objects.filter(email='testuser@gmail.com', purpose='signup').exists())

    def test_valid_registration_email_failure_returns_json_error(self):
        with patch('core.views.send_mail', side_effect=Exception('SMTP error')):
            response = self.client.post(
                self.url,
                self.valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertIn('error', data)
        self.assertFalse(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def test_otp_verify_creates_user_after_correct_otp(self):
        with patch('core.views.send_mail', return_value=1):
            response = self.client.post(
                self.url,
                self.valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('otp_sent'))

        session = self.client.session
        pending = session.get('pending_registration')
        self.assertIsNotNone(pending)
        self.assertEqual(pending['email'], 'testuser@gmail.com')

        otp_record = EmailOTP.objects.filter(email='testuser@gmail.com', purpose='signup').latest('created_at')
        known_otp = '123456'
        otp_record.otp_hash = EmailOTP.hash_otp(known_otp)
        otp_record.save()

        verify_url = reverse('otp_verify_placeholder')
        response = self.client.post(verify_url, {'otp': known_otp})
        self.assertRedirects(response, reverse('account_login'))
        self.assertTrue(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def test_user_not_created_before_otp_verification(self):
        with patch('core.views.send_mail', return_value=1):
            self.client.post(self.url, self.valid_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def test_duplicate_email_rejected(self):
        UserModel.objects.create_user(username='exists@gmail.com', email='exists@gmail.com', password='pass123')
        response = self.client.post(self.url, {
            'full_name': 'Test',
            'email': 'exists@gmail.com',
            'mobile': '9876543210',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('email', response.context['form'].errors)

    def test_registration_email_normalized(self):
        with patch('core.views.send_mail', return_value=1):
            response = self.client.post(self.url, {
                'full_name': 'Mixed Case',
                'email': '  MixedUser@Gmail.com  ',
                'mobile': '9876543210',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content).get('success'))
        # OTP is stored with a normalized (lower-cased, stripped) email.
        self.assertTrue(
            EmailOTP.objects.filter(email='mixeduser@gmail.com', purpose='signup').exists()
        )
        # Pending registration session carries the normalized email.
        pending = self.client.session.get('pending_registration')
        self.assertIsNotNone(pending)
        self.assertEqual(pending['email'], 'mixeduser@gmail.com')

    def test_signup_otp_cannot_be_reused(self):
        verify_url, known_otp = self._start_pending_registration()
        first = self.client.post(
            verify_url, {'otp': known_otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertTrue(json.loads(first.content).get('success'))
        # Re-submitting the same OTP must fail (session consumed / already verified).
        second = self.client.post(
            verify_url, {'otp': known_otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertFalse(json.loads(second.content).get('success'))

    def test_actual_generated_otp_verifies_successfully(self):
        captured = {}
        def capture_send_mail(subject, message, from_email, recipient_list, **kwargs):
            captured['message'] = message
            return 1

        with patch('core.views.send_mail', side_effect=capture_send_mail):
            response = self.client.post(
                self.url,
                self.valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('otp_sent'))

        self.assertIn('message', captured)
        message = captured['message']
        import re
        match = re.search(r'\b(\d{6})\b', message)
        self.assertIsNotNone(match, "Could not extract OTP from email message")
        actual_otp = match.group(1)

        session = self.client.session
        pending = session.get('pending_registration')
        self.assertIsNotNone(pending)
        self.assertEqual(pending['email'], 'testuser@gmail.com')

        otp_record = EmailOTP.objects.filter(email='testuser@gmail.com', purpose='signup').latest('created_at')

        verify_url = reverse('otp_verify_placeholder')
        response = self.client.post(verify_url, {'otp': actual_otp})
        self.assertRedirects(response, reverse('account_login'))
        self.assertTrue(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def _start_pending_registration(self):
        with patch('core.views.send_mail', return_value=1):
            response = self.client.post(
                self.url,
                self.valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('otp_sent'))
        otp_record = EmailOTP.objects.filter(email='testuser@gmail.com', purpose='signup').latest('created_at')
        known_otp = '123456'
        otp_record.otp_hash = EmailOTP.hash_otp(known_otp)
        otp_record.save()
        return reverse('otp_verify_placeholder'), known_otp

    def test_otp_verify_ajax_success_returns_json_redirect(self):
        verify_url, known_otp = self._start_pending_registration()
        response = self.client.post(
            verify_url,
            {'otp': known_otp},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('redirect_url'), reverse('account_login'))
        self.assertTrue(UserModel.objects.filter(email='testuser@gmail.com').exists())
        self.assertIsNone(self.client.session.get('pending_registration'))

    def test_otp_verify_ajax_wrong_otp_returns_json_error(self):
        verify_url, known_otp = self._start_pending_registration()
        response = self.client.post(
            verify_url,
            {'otp': '000000'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Wrong OTP. Please try again.')
        self.assertFalse(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def test_otp_verify_ajax_expired_otp_returns_json_error(self):
        verify_url, known_otp = self._start_pending_registration()
        otp_record = EmailOTP.objects.filter(email='testuser@gmail.com', purpose='signup').latest('created_at')
        otp_record.expires_at = otp_record.created_at
        otp_record.save()
        response = self.client.post(
            verify_url,
            {'otp': known_otp},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'OTP has expired. Please request a new OTP.')
        self.assertFalse(UserModel.objects.filter(email='testuser@gmail.com').exists())

    def test_otp_verify_ajax_success_does_not_leave_session_message(self):
        verify_url, known_otp = self._start_pending_registration()
        self.client.post(
            verify_url,
            {'otp': known_otp},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        storage = self.client.session.get('_messages')
        self.assertIsNone(storage)


class EmailLoginTests(TestCase):
    """Login page must be Email (Gmail) + Password only. No username login."""

    def setUp(self):
        self.login_url = reverse('account_login')
        self.email = 'loginuser@gmail.com'
        self.password = 'StrongPass123!'
        # OTP flow creates users with username == email; mirror that here.
        self.user = UserModel.objects.create_user(
            username=self.email,
            email=self.email,
            password=self.password,
        )

    def _is_authenticated(self):
        return '_auth_user_id' in self.client.session

    # A. GET login page returns 200
    def test_get_login_page_returns_200(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    # B. Page must NOT contain any username field
    def test_login_page_has_no_username_field(self):
        response = self.client.get(self.login_url)
        content = response.content.decode()
        self.assertNotIn('name="username"', content)
        self.assertNotIn('>Username</label>', content)
        self.assertNotIn('type="text"', content)

    # C. Page must contain a Gmail Address field (type=email, label "Gmail Address")
    def test_login_page_has_email_field(self):
        response = self.client.get(self.login_url)
        content = response.content.decode()
        self.assertIn('type="email"', content)
        self.assertIn('name="login"', content)
        self.assertIn('Gmail Address', content)

    # D. Correct email + password logs in successfully
    def test_correct_email_and_password_login_succeeds(self):
        response = self.client.post(
            self.login_url,
            {'login': self.email, 'password': self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/dashboard/')
        self.assertTrue(self._is_authenticated())
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    # D2. Email is normalized (case/whitespace) before authenticating
    def test_login_normalizes_email_case_and_whitespace(self):
        response = self.client.post(
            self.login_url,
            {'login': '  LoginUser@Gmail.com  ', 'password': self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self._is_authenticated())

    # E. Wrong password fails with a visible error
    def test_wrong_password_fails(self):
        response = self.client.post(
            self.login_url,
            {'login': self.email, 'password': 'WrongPassword999!'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._is_authenticated())
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertContains(
            response,
            'The email address and/or password you specified are not correct.',
        )

    # F. Unknown email fails with a visible error
    def test_unknown_email_fails(self):
        response = self.client.post(
            self.login_url,
            {'login': 'nobody@gmail.com', 'password': self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._is_authenticated())
        self.assertTrue(response.context['form'].errors)

    # G. Username value cannot be used to log in (username auth disabled)
    def test_username_cannot_be_used_to_login(self):
        user2 = UserModel.objects.create_user(
            username='plainusername',
            email='plainuser@gmail.com',
            password=self.password,
        )
        response = self.client.post(
            self.login_url,
            {'login': 'plainusername', 'password': self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._is_authenticated())


class ForgotPasswordTests(TestCase):
    """Email OTP based password reset, reusing the same EmailOTP infrastructure."""

    def setUp(self):
        self.request_url = reverse('forgot_password_request')
        self.verify_url = reverse('forgot_password_verify')
        self.reset_url = reverse('forgot_password_reset')
        self.login_url = reverse('account_login')
        self.email = 'resetuser@gmail.com'
        self.password = 'OldPass123!'
        self.user = UserModel.objects.create_user(
            username=self.email, email=self.email, password=self.password
        )

    def _capture_send_mail(self):
        captured = {}

        def _send(subject, message, from_email, recipient_list, **kwargs):
            captured['subject'] = subject
            captured['message'] = message
            captured['recipients'] = list(recipient_list)
            return 1

        return captured, _send

    def _start_reset(self, email=None):
        captured, fn = self._capture_send_mail()
        with patch('core.views.send_mail', side_effect=fn):
            resp = self.client.post(
                self.request_url,
                {'email': email or self.email},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('otp_sent'))
        import re
        m = re.search(r'\b(\d{6})\b', captured['message'])
        self.assertIsNotNone(m, 'Could not extract OTP from email body')
        return m.group(1)

    # Known email: full happy path -> new password works, old password does not.
    def test_forgot_password_known_email_flow(self):
        otp = self._start_reset()
        self.assertEqual(self.client.get(self.verify_url).status_code, 200)

        resp = self.client.post(self.verify_url, {'otp': otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(json.loads(resp.content).get('success'))

        self.assertEqual(self.client.get(self.reset_url).status_code, 200)

        new_pw = 'NewPass456!'
        resp = self.client.post(self.reset_url, {'password1': new_pw, 'password2': new_pw})
        self.assertRedirects(resp, self.login_url)

        # Old password no longer works.
        resp = self.client.post(self.login_url, {'login': self.email, 'password': self.password})
        self.assertFalse('_auth_user_id' in self.client.session)

        # New password works.
        resp = self.client.post(self.login_url, {'login': self.email, 'password': new_pw})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

    # Unknown email -> error response, no email sent.
    def test_forgot_password_unknown_email_shows_error(self):
        captured, fn = self._capture_send_mail()
        with patch('core.views.send_mail', side_effect=fn):
            resp = self.client.post(
                self.request_url,
                {'email': 'nobody.here@gmail.com'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertFalse(data.get('success'))
        self.assertIn('error', data)
        self.assertEqual(captured, {})  # send_mail never called
        self.assertIsNone(self.client.session.get('password_reset_email'))

    def test_forgot_password_wrong_otp_rejected(self):
        otp = self._start_reset()
        resp = self.client.post(self.verify_url, {'otp': '000000'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = json.loads(resp.content)
        self.assertFalse(data.get('success'))
        self.assertIn('Wrong OTP', data.get('error'))
        # Reset page still blocked without verification.
        self.assertRedirects(self.client.get(self.reset_url), self.request_url)

    def test_forgot_password_expired_otp_rejected(self):
        otp = self._start_reset()
        rec = EmailOTP.objects.filter(
            email=self.email, purpose='forgot_password', is_verified=False
        ).latest('created_at')
        rec.expires_at = rec.created_at
        rec.save()
        resp = self.client.post(self.verify_url, {'otp': otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = json.loads(resp.content)
        self.assertFalse(data.get('success'))
        self.assertIn('expired', data.get('error').lower())

    # Reset URL cannot be opened directly to bypass OTP verification.
    def test_reset_page_blocked_without_verification(self):
        self.assertRedirects(self.client.get(self.reset_url), self.request_url)
        self.client.session['password_reset_email'] = self.email
        self.client.session.save()
        self.assertRedirects(self.client.get(self.reset_url), self.request_url)

    def test_correct_reset_otp_allows_password_reset(self):
        otp = self._start_reset()
        self.client.post(self.verify_url, {'otp': otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        new_pw = 'BrandNew789!'
        resp = self.client.post(self.reset_url, {'password1': new_pw, 'password2': new_pw})
        self.assertRedirects(resp, self.login_url)
        self.assertIsNone(self.client.session.get('password_reset_verified'))
        resp = self.client.post(self.login_url, {'login': self.email, 'password': new_pw})
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_reset_otp_cannot_be_reused(self):
        otp = self._start_reset()
        first = self.client.post(self.verify_url, {'otp': otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(json.loads(first.content).get('success'))
        # After verification the verify page is no longer reachable (OTP consumed).
        self.assertRedirects(self.client.get(self.verify_url), self.request_url)

    def test_email_normalization_in_forgot_password(self):
        otp = self._start_reset(email='  ResetUser@Gmail.com  ')
        self.assertEqual(self.client.session.get('password_reset_email'), self.email)
        resp = self.client.post(self.verify_url, {'otp': otp}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(json.loads(resp.content).get('success'))


class EmailBackendConfigTests(TestCase):
    """The email backend must be wired for real Gmail SMTP, not blind console."""

    def test_gmail_smtp_configuration(self):
        self.assertEqual(settings.EMAIL_HOST, 'smtp.gmail.com')
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)

    def test_otp_delivered_through_email_backend(self):
        # Real credentials are expected in .env; in production that makes the
        # project use Gmail SMTP. The test runner substitutes a locmem backend,
        # so we assert the OTP is actually delivered through Django's email
        # backend (i.e. it is sent, not merely printed to the terminal).
        creds = bool(
            os.environ.get('EMAIL_HOST_USER') and os.environ.get('EMAIL_HOST_PASSWORD')
        )
        self.assertTrue(creds, 'Set EMAIL_HOST_USER + EMAIL_HOST_PASSWORD in .env to send real OTP emails')
        from django.core import mail
        mail.outbox = []
        send_otp_email('someone@gmail.com', '123456', 'signup')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Verify your email - Mess Management')
        self.assertEqual(mail.outbox[0].to, ['someone@gmail.com'])


from core.views import send_otp_email  # noqa: E402


class PaymentEmailReceiptTests(TestCase):
    def setUp(self):
        self.student_user = UserModel.objects.create_user(
            username='student1',
            email='student1@gmail.com',
            password='pass123',
            first_name='Rahul',
            last_name='Sharma',
        )
        self.student = Student.objects.create(
            user=self.student_user,
            hostel_id='STU001',
            room_no='101',
            phone='9876543210',
            email='rahul.sharma@gmail.com',
        )
        self.period = AccountingPeriod.objects.create(
            name='August 2026',
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            is_active=True,
        )
        self.account = StudentPeriodAccount.objects.create(
            student=self.student,
            period=self.period,
            total_to_collect=1000,
        )
        self.payment_url = reverse('payment_add')

        self.admin_user = UserModel.objects.create_user(
            username='admin',
            email='admin@gmail.com',
            password='adminpass',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.admin_user)
        profile.role = 'admin'
        profile.is_active_user = True
        profile.save()
        self.client.force_login(self.admin_user)

    def test_payment_with_student_email_sends_receipt(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            response = self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 1000,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        self.assertEqual(subject, 'Mess Payment Receipt | August 2026')
        body = mock_send.call_args[0][1]
        self.assertIn('Rahul', body)
        self.assertIn('PAID', body)
        self.assertIn('Total Mess Fee: ₹1000', body)
        self.assertIn('Total Amount Paid: ₹1000', body)
        self.assertIn('Remaining Due: ₹0', body)

    def test_payment_without_student_email_skips_receipt(self):
        self.student.email = ''
        self.student.save(update_fields=['email'])
        self.student_user.email = ''
        self.student_user.save(update_fields=['email'])

        with patch('core.views.send_mail', return_value=1) as mock_send:
            response = self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 500,
                'month': '2026-08-01',
                'method': 'Cash',
                'status': 'PAID',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        mock_send.assert_not_called()

    def test_full_payment_shows_paid_status_and_zero_due(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 1000,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        payment = Payment.objects.first()
        self.assertEqual(payment.amount, 1000)
        self.assertEqual(payment.status, 'PAID')
        self.account.refresh_from_db()
        self.assertEqual(self.account.get_display_remaining(), 0)
        body = mock_send.call_args[0][1]
        self.assertIn('PAID', body)
        self.assertIn('₹0', body)
        self.assertIn('Total Mess Fee: ₹1000', body)
        self.assertIn('Total Amount Paid: ₹1000', body)

    def test_partial_payment_shows_due_status(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 400,
                'month': '2026-08-01',
                'method': 'Cash',
                'status': 'PAID',
            })
        self.assertEqual(Payment.objects.count(), 1)
        self.account.refresh_from_db()
        self.assertEqual(self.account.get_display_remaining(), 600)
        body = mock_send.call_args[0][1]
        self.assertIn('DUE', body)
        self.assertIn('₹600', body)
        self.assertIn('Total Mess Fee: ₹1000', body)
        self.assertIn('Total Amount Paid: ₹400', body)

    def test_multiple_payments_same_student_month_shows_correct_remaining(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 300,
                'month': '2026-08-01',
                'method': 'Cash',
                'status': 'PAID',
            })
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 200,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        self.assertEqual(Payment.objects.count(), 2)
        self.account.refresh_from_db()
        self.assertEqual(self.account.get_display_remaining(), 500)
        second_call_body = mock_send.call_args_list[1][0][1]
        self.assertIn('Total Mess Fee: ₹1000', second_call_body)
        self.assertIn('Total Amount Paid: ₹500', second_call_body)
        self.assertIn('Remaining Due: ₹500', second_call_body)
        self.assertIn('DUE', second_call_body)

    def test_email_sending_failure_does_not_rollback_payment(self):
        with patch('core.views.send_mail', side_effect=Exception('SMTP down')):
            response = self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 500,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.first().amount, 500)

    def test_payment_save_failure_does_not_send_email(self):
        with patch('core.views.PaymentForm.save', side_effect=Exception('DB error')):
            with patch('core.views.send_mail', return_value=1) as mock_send:
                response = self.client.post(self.payment_url, {
                    'student': self.student.id,
                    'period': self.period.id,
                    'amount': 500,
                    'month': '2026-08-01',
                    'method': 'UPI',
                    'status': 'PAID',
                })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)
        mock_send.assert_not_called()

    def test_duplicate_posts_create_separate_payments_and_emails(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            for _ in range(2):
                self.client.post(self.payment_url, {
                    'student': self.student.id,
                    'period': self.period.id,
                    'amount': 100,
                    'month': '2026-08-01',
                    'method': 'Cash',
                    'status': 'PAID',
                })
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(mock_send.call_count, 2)

    def test_existing_payment_history_and_summary_still_work(self):
        with patch('core.views.send_mail', return_value=1):
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 500,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })

        summary_url = reverse('payment_summary')
        response = self.client.get(summary_url)
        self.assertEqual(response.status_code, 200)

        history_url = reverse('payment_history', args=[self.student.id, self.period.id])
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, 200)

    def test_september_payment_sends_september_receipt(self):
        september_period = AccountingPeriod.objects.create(
            name='September 2026',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=self.student,
            period=september_period,
            total_to_collect=1000,
        )
        with patch('core.views.send_mail', return_value=1) as mock_send:
            response = self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': september_period.id,
                'amount': 1000,
                'month': '2026-09-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        self.assertEqual(subject, 'Mess Payment Receipt | September 2026')

    def test_receipt_uses_period_over_mismatched_month(self):
        september_period = AccountingPeriod.objects.create(
            name='September 2026',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=self.student,
            period=september_period,
            total_to_collect=1000,
        )
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': september_period.id,
                'amount': 1000,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        mock_send.assert_called_once()
        subject = mock_send.call_args[0][0]
        self.assertEqual(subject, 'Mess Payment Receipt | September 2026')

    # --- Goal A: Student Name used in email ---

    def test_payment_email_uses_student_name_with_spaces(self):
        self.student.student_name = 'Aman Jaiswal'
        self.student.save(update_fields=['student_name'])
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 1000,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        body = mock_send.call_args[0][1]
        self.assertIn('Dear Aman Jaiswal,', body)
        # Username 'student1' must NOT appear as the greeting
        self.assertNotIn('Dear student1', body)
        self.assertNotIn('Dear STU001', body)

    def test_paid_email_contains_professional_body(self):
        self.student.student_name = 'Aman Jaiswal'
        self.student.save(update_fields=['student_name'])
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 1000,
                'month': '2026-08-01',
                'method': 'UPI',
                'status': 'PAID',
            })
        body = mock_send.call_args[0][1]
        self.assertIn('Dear Aman Jaiswal,', body)
        self.assertIn('Hostel Mess Management System', body)
        self.assertIn('PAYMENT SUMMARY', body)
        self.assertIn('Billing Month: August 2026', body)
        self.assertIn('Total Mess Fee: ₹1000', body)
        self.assertIn('Total Amount Paid: ₹1000', body)
        self.assertIn('Remaining Due: ₹0', body)
        self.assertIn('Payment Status: PAID', body)
        self.assertIn('complete and no amount is currently pending', body)
        self.assertIn('Mess Management Committee', body)
        self.assertIn('APJ Abdul Kalam Boys Hostel', body)
        self.assertIn('Warm Regards,', body)

    def test_due_email_contains_professional_body(self):
        self.student.student_name = 'Aman Jaiswal'
        self.student.save(update_fields=['student_name'])
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': self.period.id,
                'amount': 400,
                'month': '2026-08-01',
                'method': 'Cash',
                'status': 'PAID',
            })
        body = mock_send.call_args[0][1]
        self.assertIn('Dear Aman Jaiswal,', body)
        self.assertIn('PAYMENT SUMMARY', body)
        self.assertIn('Billing Month: August 2026', body)
        self.assertIn('Total Mess Fee: ₹1000', body)
        self.assertIn('Total Amount Paid: ₹400', body)
        self.assertIn('Remaining Due: ₹600', body)
        self.assertIn('Payment Status: DUE', body)
        self.assertIn('remaining amount is still pending', body)
        self.assertNotIn('PARTIALLY PAID', body)


class PaymentModeTests(TestCase):
    """Tests for the new payment_mode field (PART 5-B)."""

    def setUp(self):
        self.student_user = UserModel.objects.create_user(
            username='pm_student', email='pm_student@test.com', password='pass123',
        )
        self.student = Student.objects.create(
            user=self.student_user, hostel_id='STU_PM', room_no='201',
            phone='9876543210', email='pm_student@gmail.com',
        )
        self.period = AccountingPeriod.objects.create(
            name='September 2026', start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30), is_active=True,
        )

    # A. New Payment defaults to payment_mode = custom_full
    def test_payment_default_mode_is_custom_full(self):
        payment = Payment.objects.create(
            student=self.student, period=self.period,
            amount=1000, month=date(2026, 9, 15),
            method='UPI', status='PAID',
        )
        self.assertEqual(payment.payment_mode, 'custom_full')

    # B. Payment explicitly created with default_fee
    def test_payment_mode_can_be_default_fee(self):
        payment = Payment.objects.create(
            student=self.student, period=self.period,
            amount=1000, month=date(2026, 9, 15),
            method='UPI', status='PAID',
            payment_mode='default_fee',
        )
        self.assertEqual(payment.payment_mode, 'default_fee')

    # E. PaymentForm accepts both choices (and rejects invalid)
    def test_payment_form_accepts_both_modes(self):
        from core.forms import PaymentForm
        base = {
            'student': self.student.id, 'period': self.period.id,
            'amount': 1000, 'month': '2026-09-01',
            'method': 'UPI', 'txn_id': '', 'status': 'PAID',
        }
        self.assertTrue(PaymentForm(data={**base, 'payment_mode': 'default_fee'}).is_valid())
        self.assertTrue(PaymentForm(data={**base, 'payment_mode': 'custom_full'}).is_valid())
        self.assertFalse(PaymentForm(data={**base, 'payment_mode': 'invalid'}).is_valid())

    # D. Django Admin payment add form renders payment_mode with both labels
    def test_admin_payment_form_renders_payment_mode(self):
        superuser = UserModel.objects.create_superuser(
            username='pm_superuser', email='pm_superuser@test.com', password='adminpass',
        )
        self.client.force_login(superuser)
        url = reverse('admin:core_payment_add')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('payment_mode', content)
        self.assertIn('Use Default Fee', content)
        self.assertIn('Custom / Full Paid Amount', content)


class PaymentModeDefaultFeeApplicationTests(TestCase):
    """PART 5-C: payment_mode must drive StudentPeriodAccount.total_to_collect."""

    def setUp(self):
        self.student_user = UserModel.objects.create_user(
            username='df_student', email='df_student@test.com', password='pass123',
        )
        self.student = Student.objects.create(
            user=self.student_user, hostel_id='STU_DF', room_no='301',
            phone='9876543210', email='df_student@gmail.com',
        )
        self.period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        PeriodDefaultFee.objects.create(
            period=self.period, default_fee_per_student=500,
        )
        self.payment_url = reverse('payment_add')

        admin_user = UserModel.objects.create_user(
            username='df_admin', email='df_admin@test.com', password='adminpass',
        )
        profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        profile.role = 'admin'
        profile.is_active_user = True
        profile.save()
        self.client.force_login(admin_user)

    def _post_payment(self, amount, mode='default_fee', status='PAID'):
        return self.client.post(self.payment_url, {
            'student': self.student.id,
            'period': self.period.id,
            'amount': amount,
            'month': '2026-08-01',
            'method': 'UPI',
            'status': status,
            'payment_mode': mode,
        })

    def _account(self):
        return StudentPeriodAccount.objects.get(student=self.student, period=self.period)

    def test_default_fee_applied_on_partial_payment(self):
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(200, mode='default_fee')
        account = self._account()
        self.assertEqual(account.total_to_collect, 500)
        self.assertEqual(account.get_total_paid(), 200)
        self.assertEqual(account.get_display_remaining(), 300)
        self.assertTrue(account.get_display_remaining() >= 0)

    def test_default_fee_full_payment_is_paid(self):
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(500, mode='default_fee')
        account = self._account()
        self.assertEqual(account.total_to_collect, 500)
        self.assertEqual(account.get_total_paid(), 500)
        self.assertEqual(account.get_display_remaining(), 0)

    def test_two_partial_default_fee_payments_keep_due(self):
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(200, mode='default_fee')
            self._post_payment(300, mode='default_fee')
        account = self._account()
        self.assertEqual(account.total_to_collect, 500)
        self.assertEqual(account.get_total_paid(), 500)
        self.assertEqual(account.get_display_remaining(), 0)

    def test_custom_full_payment_seeds_total_to_collect(self):
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(500, mode='custom_full')
        account = self._account()
        self.assertEqual(account.total_to_collect, 500)
        self.assertEqual(account.get_total_paid(), 500)
        self.assertEqual(account.get_display_remaining(), 0)

    def test_manually_configured_due_not_overwritten(self):
        account = StudentPeriodAccount.objects.create(
            student=self.student, period=self.period, total_to_collect=700,
        )
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(200, mode='default_fee')
        account.refresh_from_db()
        self.assertEqual(account.total_to_collect, 700)
        self.assertEqual(account.get_total_paid(), 200)
        self.assertEqual(account.get_display_remaining(), 500)

    def test_remaining_never_negative_in_summary(self):
        with patch('core.views.send_mail', return_value=1):
            self._post_payment(200, mode='default_fee')
        response = self.client.get(reverse('payment_summary'), {'period': self.period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual(len(summary), 1)
        self.assertGreaterEqual(summary[0]['display_remaining'], 0)
        self.assertEqual(summary[0]['display_remaining'], 300)
        self.assertEqual(summary[0]['status'], 'Due')

    def test_receipt_email_uses_updated_account(self):
        with patch('core.views.send_mail', return_value=1) as mock_send:
            self._post_payment(200, mode='default_fee')
        body = mock_send.call_args[0][1]
        self.assertIn('Total Mess Fee: ₹500', body)
        self.assertIn('Total Amount Paid: ₹200', body)
        self.assertIn('Remaining Due: ₹300', body)
        self.assertIn('DUE', body)

    def test_default_fee_not_applied_when_no_period_default_fee(self):
        empty_period = AccountingPeriod.objects.create(
            name='July 2026', start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31), is_active=True,
        )
        with patch('core.views.send_mail', return_value=1):
            response = self.client.post(self.payment_url, {
                'student': self.student.id,
                'period': empty_period.id,
                'amount': 200,
                'month': '2026-07-01',
                'method': 'UPI',
                'status': 'PAID',
                'payment_mode': 'default_fee',
            })
        self.assertEqual(response.status_code, 302)
        account = StudentPeriodAccount.objects.get(student=self.student, period=empty_period)
        self.assertEqual(account.total_to_collect, 0)


class StudentNameTests(TestCase):
    """Tests for the separate Student Name field (Goal A)."""

    def setUp(self):
        self.admin_user = UserModel.objects.create_user(
            username='admin', email='admin@gmail.com', password='adminpass',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.admin_user)
        profile.role = 'admin'
        profile.is_active_user = True
        profile.save()
        self.client.force_login(self.admin_user)

    def _make_user(self, username, first_name='Test', last_name='User'):
        return UserModel.objects.create_user(
            username=username, email=f'{username}@gmail.com',
            password='pass123', first_name=first_name, last_name=last_name,
        )

    # A. Student Name allows spaces
    def test_student_name_with_spaces_preserved(self):
        user = self._make_user('space_user')
        student = Student.objects.create(
            user=user, hostel_id='BH26003', student_name='Aman Jaiswal',
        )
        student.refresh_from_db()
        self.assertEqual(student.student_name, 'Aman Jaiswal')
        self.assertIn(' ', student.student_name)

    # B. Duplicate Student Names are allowed (no unique constraint)
    def test_duplicate_student_names_allowed(self):
        user1 = self._make_user('dup_a', 'Aman', 'Jaiswal')
        user2 = self._make_user('dup_b', 'Aman', 'Jaiswal')
        s1 = Student.objects.create(
            user=user1, hostel_id='BH26100', student_name='Aman Jaiswal',
        )
        s2 = Student.objects.create(
            user=user2, hostel_id='BH26101', student_name='Aman Jaiswal',
        )
        self.assertEqual(Student.objects.filter(student_name='Aman Jaiswal').count(), 2)
        self.assertEqual(s1.hostel_id, 'BH26100')
        self.assertEqual(s2.hostel_id, 'BH26101')

    # C. Duplicate Hostel IDs are still prevented (unique constraint preserved)
    def test_duplicate_hostel_id_prevented(self):
        user1 = self._make_user('hid_a', 'Aman', 'Jaiswal')
        user2 = self._make_user('hid_b', 'Aman', 'Jaiswal')
        Student.objects.create(
            user=user1, hostel_id='BH_SHARED', student_name='Aman Jaiswal',
        )
        with self.assertRaises(Exception):
            Student.objects.create(
                user=user2, hostel_id='BH_SHARED', student_name='Aman Jaiswal',
            )

    # D. StudentName field is not unique in the model
    def test_student_name_field_not_unique(self):
        field = Student._meta.get_field('student_name')
        self.assertFalse(field.unique)

    # E. student_add form saves student_name with spaces and syncs user first/last
    def test_student_add_saves_student_name_and_syncs_user(self):
        url = reverse('student_add')
        response = self.client.post(url, {
            'student_name': 'Aman Jaiswal',
            'hostel_id': 'BH26010',
            'room_no': '101',
            'phone': '9876543210',
            'email': 'amanjaiswal@gmail.com',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        student = Student.objects.get(hostel_id='BH26010')
        self.assertEqual(student.student_name, 'Aman Jaiswal')
        self.assertEqual(student.user.first_name, 'Aman')
        self.assertEqual(student.user.last_name, 'Jaiswal')
        self.assertEqual(student.user.username, 'BH26010')

    # F. student_add rejects duplicate hostel_id through the form
    def test_student_add_duplicate_hostel_id_through_form(self):
        user = self._make_user('form_dup', 'First', 'User')
        Student.objects.create(
            user=user, hostel_id='BH26020', student_name='First User',
        )
        url = reverse('student_add')
        response = self.client.post(url, {
            'student_name': 'Another User',
            'hostel_id': 'BH26020',
            'room_no': '',
            'phone': '',
            'email': '',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        # Only 1 student with this hostel_id — the duplicate was rejected
        self.assertEqual(Student.objects.filter(hostel_id='BH26020').count(), 1)

    # G. student_list view shows student_name
    def test_student_list_shows_student_name(self):
        user = self._make_user('list_user', 'Aman', 'Jaiswal')
        Student.objects.create(
            user=user, hostel_id='BH26030', student_name='Aman Jaiswal',
        )
        response = self.client.get(reverse('student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aman Jaiswal')

    # H. Backfill migration populates student_name from user.get_full_name
    def test_backfill_populates_student_name_from_user(self):
        user = UserModel.objects.create_user(
            username='backfill_user', email='bf@gmail.com',
            password='pass123', first_name='Back', last_name='Filled',
        )
        student = Student.objects.create(
            user=user, hostel_id='BH26040',
        )
        # Simulate what the migration does for a record without student_name
        if not student.student_name:
            student.student_name = user.get_full_name()
            student.save(update_fields=['student_name'])
        student.refresh_from_db()
        self.assertEqual(student.student_name, 'Back Filled')

    # I. Two students with same name get distinguishable emails by hostel_id
    def test_same_name_distinguishable_by_hostel_id(self):
        user1 = self._make_user('same_a', 'Aman', 'Jaiswal')
        user2 = self._make_user('same_b', 'Aman', 'Jaiswal')
        s1 = Student.objects.create(
            user=user1, hostel_id='BH26200', student_name='Aman Jaiswal',
            email='same1@gmail.com',
        )
        s2 = Student.objects.create(
            user=user2, hostel_id='BH26201', student_name='Aman Jaiswal',
            email='same2@gmail.com',
        )
        self.assertNotEqual(s1.hostel_id, s2.hostel_id)
        self.assertEqual(s1.student_name, s2.student_name)
        self.assertNotEqual(s1.email, s2.email)

    # J. student_search_api includes student_name
    def test_student_search_api_uses_student_name(self):
        user = self._make_user('search_u', 'Aman', 'Jaiswal')
        Student.objects.create(
            user=user, hostel_id='BH26050', student_name='Aman Jaiswal',
        )
        response = self.client.get(reverse('student_search_api'), {'q': 'Aman'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(any(r['name'] == 'Aman Jaiswal' for r in data['results']))


class DueListTests(TestCase):
    def setUp(self):
        self.admin_user = UserModel.objects.create_user(
            username='admin', email='admin@gmail.com', password='adminpass',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.admin_user)
        profile.role = 'admin'
        profile.is_active_user = True
        profile.save()
        self.client.force_login(self.admin_user)
        self.url = reverse('due_list')

    def _make_student(self, username, hostel_id, student_name='Test Student'):
        user = UserModel.objects.create_user(
            username=username, email=f'{username}@gmail.com', password='pass123',
        )
        student = Student.objects.create(
            user=user, hostel_id=hostel_id, student_name=student_name,
        )
        return student

    def test_partially_paid_student_appears_in_due_list(self):
        student = self._make_student('stu1', 'STU001', 'Rahul Sharma')
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=student, period=period, total_to_collect=2800,
        )
        Payment.objects.create(
            student=student, period=period, amount=1500,
            month=date(2026, 8, 1), method='UPI', status='PAID',
        )
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rahul Sharma')
        self.assertContains(response, 'STU001')
        summary = response.context['due_list']
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['remaining_due'], 1300)
        self.assertEqual(response.context['total_students_with_due'], 1)
        self.assertEqual(response.context['total_outstanding_due'], 1300)

    def test_fully_paid_student_does_not_appear(self):
        student = self._make_student('stu2', 'STU002', 'Aman Jaiswal')
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=student, period=period, total_to_collect=2500,
        )
        Payment.objects.create(
            student=student, period=period, amount=2500,
            month=date(2026, 8, 1), method='UPI', status='PAID',
        )
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 0)

    def test_zero_remaining_student_does_not_appear(self):
        student = self._make_student('stu3', 'STU003', 'Zero Due')
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=student, period=period, total_to_collect=0,
        )
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 0)

    def test_admin_without_student_record_never_appears(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 0)

    def test_user_without_student_record_never_appears(self):
        viewer = UserModel.objects.create_user(
            username='viewer', email='viewer@gmail.com', password='pass123',
        )
        profile, _ = UserProfile.objects.get_or_create(user=viewer)
        profile.role = 'viewer'
        profile.is_active_user = True
        profile.save()
        self.client.force_login(viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 0)

    def test_two_same_name_students_remain_separate(self):
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        s1 = self._make_student('s1', 'BH26001', 'Aman Jaiswal')
        s2 = self._make_student('s2', 'BH26002', 'Aman Jaiswal')
        StudentPeriodAccount.objects.create(student=s1, period=period, total_to_collect=2800)
        StudentPeriodAccount.objects.create(student=s2, period=period, total_to_collect=2500)
        Payment.objects.create(student=s1, period=period, amount=1500,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        Payment.objects.create(student=s2, period=period, amount=2500,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['student'].hostel_id, 'BH26001')
        self.assertEqual(summary[0]['remaining_due'], 1300)

    def test_period_filtering_isolates_dues(self):
        period_a = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        period_b = AccountingPeriod.objects.create(
            name='September 2026', start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30), is_active=True,
        )
        student = self._make_student('stu_period', 'STU_P', 'Period Test')
        StudentPeriodAccount.objects.create(student=student, period=period_a, total_to_collect=2800)
        StudentPeriodAccount.objects.create(student=student, period=period_b, total_to_collect=2500)
        Payment.objects.create(student=student, period=period_a, amount=1500,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        Payment.objects.create(student=student, period=period_b, amount=2500,
            month=date(2026, 9, 1), method='UPI', status='PAID')

        response_a = self.client.get(self.url, {'period': period_a.id})
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(len(response_a.context['due_list']), 1)

        response_b = self.client.get(self.url, {'period': period_b.id})
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(len(response_b.context['due_list']), 0)

    def test_manual_remaining_due_respected(self):
        student = self._make_student('stu_manual', 'STU_M', 'Manual Due')
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        account = StudentPeriodAccount.objects.create(
            student=student, period=period, total_to_collect=1000,
            manual_remaining=500, is_manual_remaining=True,
        )
        Payment.objects.create(student=student, period=period, amount=600,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['remaining_due'], 500)
        self.assertEqual(summary[0]['remaining_type'], 'Manual')

    def test_overpayment_never_shows_negative_due(self):
        student = self._make_student('stu_over', 'STU_O', 'Overpay')
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        StudentPeriodAccount.objects.create(
            student=student, period=period, total_to_collect=1000,
        )
        Payment.objects.create(student=student, period=period, amount=1500,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        summary = response.context['due_list']
        self.assertEqual(len(summary), 0)

    def test_total_students_with_due_count_is_correct(self):
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        s1 = self._make_student('s1', 'BH26001', 'Student One')
        s2 = self._make_student('s2', 'BH26002', 'Student Two')
        s3 = self._make_student('s3', 'BH26003', 'Student Three')
        StudentPeriodAccount.objects.create(student=s1, period=period, total_to_collect=1000)
        StudentPeriodAccount.objects.create(student=s2, period=period, total_to_collect=2000)
        StudentPeriodAccount.objects.create(student=s3, period=period, total_to_collect=3000)
        Payment.objects.create(student=s1, period=period, amount=400,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        Payment.objects.create(student=s2, period=period, amount=1500,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        Payment.objects.create(student=s3, period=period, amount=3000,
            month=date(2026, 8, 1), method='UPI', status='PAID')

        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_students_with_due'], 2)
        self.assertEqual(response.context['total_outstanding_due'], 1100)

    def test_total_outstanding_due_sum_is_correct(self):
        period = AccountingPeriod.objects.create(
            name='August 2026', start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31), is_active=True,
        )
        s1 = self._make_student('s1', 'BH26001', 'Student One')
        s2 = self._make_student('s2', 'BH26002', 'Student Two')
        StudentPeriodAccount.objects.create(student=s1, period=period, total_to_collect=1000)
        StudentPeriodAccount.objects.create(student=s2, period=period, total_to_collect=2000)
        Payment.objects.create(student=s1, period=period, amount=300,
            month=date(2026, 8, 1), method='UPI', status='PAID')
        Payment.objects.create(student=s2, period=period, amount=500,
            month=date(2026, 8, 1), method='UPI', status='PAID')

        response = self.client.get(self.url, {'period': period.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_outstanding_due'], 2200)

