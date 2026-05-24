"""Optional seed questions for Daily Challenge.

If this file exists, the bot can preload questions on first start.
Schema:
{
    "subject": str,
    "q": str,
    "a": [str, str, str, str],
    "correct": int,  # 0..3
}
"""

QUESTIONS = [
    {
        "subject": "Математика",
        "q": "2 + 2 нешеге тең?",
        "a": ["3", "4", "5", "6"],
        "correct": 1,
    },
    {
        "subject": "Физика",
        "q": "SI жүйесіндегі жылдамдық бірлігі?",
        "a": ["Ньютон", "Ватт", "м/с", "Паскаль"],
        "correct": 2,
    },
    {
        "subject": "Қазақстан тарихы",
        "q": "Қазақстан тәуелсіздігін жариялаған жыл?",
        "a": ["1986", "1991", "1995", "2001"],
        "correct": 1,
    },
]

