from app.models.core import Department


def test_required_departments_seeded(app):
    with app.app_context():
        names = {d.name for d in Department.query.all()}

        expected = {
            "Computer Science",
            "Mechatronics Engineering",
            "Science Lab Tech",
            "Food Technology",
            "Hospitality Management",
            "Electrical Engineering",
            "Mechanical Engineering",
            "Accountancy",
            "Marketing",
            "Public Administration",
            "Business Administration",
        }

        assert expected.issubset(names)