# AGENTS.md

## Project: Mess Management System (Django)

## Commands

### Python Interpreter
The venv is broken (points to Python 3.13 which is not installed). Use Python 3.14 directly:
```
C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe manage.py <command>
```

### Common Commands
```
# System check
python manage.py check

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Run development server
python manage.py runserver

# Django shell
python manage.py shell
```

## Database
- **Engine**: MySQL
- **Host**: 127.0.0.1:3306
- **Database**: mess_db
- **User**: root
- **Password**: Aman@123 (from env `MYSQL_PASSWORD`)

## Role System
- **admin**: Full access to everything
- **staff**: Access depends on assigned permissions (managed by admin)
- **viewer**: Read-only access

## Permission Fields (UserProfile model)
- can_manage_students
- can_manage_payments
- can_manage_expenses
- can_manage_purchases
- can_manage_settlements
- can_view_reports
- can_export_collection_excel
- can_export_expense_excel
- can_export_purchase_excel
- can_export_payment_excel

## Key URLs
- `/dashboard/` — Dashboard (all authenticated users)
- `/students/` — Student list (read-only for all)
- `/students/add/` — Add student (admin or staff with can_manage_students)
- `/payments/summary/` — Payment summary (read-only for all)
- `/payments/add/` — Add payment (admin or staff with can_manage_payments)
- `/users/manage/` — User management (admin only)
- `/users/<id>/permissions/` — Staff permission edit (admin only)
- `/users/activity/` — Login activity (admin only)
