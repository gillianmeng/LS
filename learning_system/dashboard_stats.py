"""管理后台首页仪表盘统计（供 AdminSite.index 注入上下文）。"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def get_admin_dashboard_stats() -> dict:
    """聚合当前库中的课程、员工、考试、培训、学习等数量。"""
    now = timezone.now()
    month_start = now - timedelta(days=30)

    def safe_count(qs):
        try:
            return qs.count()
        except Exception:
            return 0

    zeros = {
        "courses_total": 0,
        "courses_new": 0,
        "employees_total": 0,
        "employees_active": 0,
        "exams_total": 0,
        "exam_records": 0,
        "trainings_total": 0,
        "training_regs": 0,
        "learning_rows": 0,
        "completed_learn": 0,
        "focus_courses_enabled": 0,
        "focus_exams_enabled": 0,
        "focus_course_accum_rows": 0,
        "focus_course_blur_sum": 0,
        "focus_exam_sessions": 0,
        "focus_exam_sessions_forced": 0,
        "focus_exam_records_forced_zero": 0,
    }

    try:
        from django.db.models import Sum

        from courses.models import (
            Course,
            CourseFocusAccum,
            Exam,
            ExamFocusSession,
            ExamRecord,
            LearningRecord,
        )
        from shop.models import Training, TrainingRegistration
        from users.models import Employee

        course_blur = CourseFocusAccum.objects.aggregate(s=Sum("blur_count"))["s"] or 0

        return {
            "courses_total": safe_count(Course.objects.all()),
            "courses_new": safe_count(Course.objects.filter(created_at__gte=month_start)),
            "employees_total": safe_count(Employee.objects.all()),
            "employees_active": safe_count(Employee.objects.filter(is_active=True)),
            "exams_total": safe_count(Exam.objects.all()),
            "exam_records": safe_count(ExamRecord.objects.all()),
            "trainings_total": safe_count(Training.objects.all()),
            "training_regs": safe_count(TrainingRegistration.objects.all()),
            "learning_rows": safe_count(LearningRecord.objects.all()),
            "completed_learn": safe_count(LearningRecord.objects.filter(is_completed=True)),
            "focus_courses_enabled": safe_count(
                Course.objects.filter(focus_monitor_enabled=True)
            ),
            "focus_exams_enabled": safe_count(Exam.objects.filter(focus_monitor_enabled=True)),
            "focus_course_accum_rows": safe_count(CourseFocusAccum.objects.all()),
            "focus_course_blur_sum": int(course_blur),
            "focus_exam_sessions": safe_count(ExamFocusSession.objects.all()),
            "focus_exam_sessions_forced": safe_count(
                ExamFocusSession.objects.filter(force_ended=True)
            ),
            "focus_exam_records_forced_zero": safe_count(
                ExamRecord.objects.filter(focus_forced_zero=True)
            ),
        }
    except Exception:
        return zeros.copy()
