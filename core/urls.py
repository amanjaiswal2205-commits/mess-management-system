from django.urls import path
from . import views

urlpatterns = [
    # Home & Dashboard
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/export/excel/', views.students_export_excel, name='students_export_excel'),
    path('students/add/', views.student_add, name='student_add'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/toggle-active/', views.student_toggle_active, name='student_toggle_active'),
    path('settings/students/', views.mess_setting, name='mess_setting'),

    # Period Default Fee
    path('settings/default-fee/', views.period_default_fee_set, name='period_default_fee_set'),
    path('settings/default-fee/apply-unset/<int:period_id>/', views.period_default_fee_apply_unset, name='period_default_fee_apply_unset'),
    path('settings/default-fee/apply-all/<int:period_id>/', views.period_default_fee_apply_all, name='period_default_fee_apply_all'),

    # Payments
    path('payments/', views.payments_list, name='payments_list'),
    path('payments/export/excel/', views.payments_export_excel, name='payments_export_excel'),
    path('payments/summary/', views.payment_summary, name='payment_summary'),
    path('payments/add/', views.payment_add, name='payment_add'),
    path('payments/export/excel/', views.payments_export_excel, name='payments_export_excel'),
    path('payments/export/summary/excel/', views.payments_summary_export_excel, name='payments_summary_export_excel'),
    path('payments/export/summary/excel/', views.payments_summary_export_excel, name='payments_summary_export_excel'),
    path('payments/due/<int:student_id>/<int:period_id>/', views.payment_due_edit, name='payment_due_edit'),
    path('payments/history/<int:student_id>/<int:period_id>/', views.payment_history, name='payment_history'),
    path('api/students/search/', views.student_search_api, name='student_search_api'),

    # Purchases
    path('purchases/', views.purchases_list, name='purchases_list'),
    path('purchases/add/', views.purchase_add, name='purchase_add'),
    path('purchases/<int:pk>/edit/', views.purchase_edit, name='purchase_edit'),
    path('purchases/export/excel/', views.purchases_export_excel, name='purchases_export_excel'),

    # Expenses
    path('expenses/', views.expenses_list, name='expenses_list'),
    path('expenses/export/excel/', views.expenses_export_excel, name='expenses_export_excel'),

    # Settlements
    path('settlements/', views.settlement_list, name='settlement_list'),
    path('settlements/export/excel/', views.settlements_export_excel, name='settlements_export_excel'),

    # Settlement generation (explicit user action required via form)
    path('settlement/<int:year>/<int:month>/<int:closed_days>/', views.auto_settlement, name='auto_settlement_with_closed'),
    path('settlement/period/<int:period_id>/', views.period_settlement, name='period_settlement'),

    # Reports
    path('reports/purchases/', views.purchases_report, name='purchases_report'),
    path('reports/master/', views.master_report, name='master_report'),

    # User Activity (Admin Only)
    path('users/activity/', views.user_activity, name='user_activity'),

    # User Management (Admin Only)
    path('users/manage/', views.user_manage, name='user_manage'),
    path('users/<int:user_id>/change-role/', views.user_change_role, name='user_change_role'),
    path('users/<int:user_id>/toggle-account/', views.user_toggle_account, name='user_toggle_account'),
    path('users/<int:user_id>/permissions/', views.user_permissions_edit, name='user_permissions_edit'),
]