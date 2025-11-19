# This is a template for your data migration
# After running: python manage.py makemigrations chatbot --empty --name migrate_question_texts
# You'll get a file like: chatbot/migrations/0019_migrate_question_texts.py
#
# Replace the content of that file with this:

from django.db import migrations


def migrate_questions_to_translations(apps, schema_editor):
    """
    Migrate existing question_text to QuestionTranslation model
    Assume existing questions are in Kyrgyz language
    """
    Question = apps.get_model('chatbot', 'Question')
    QuestionTranslation = apps.get_model('chatbot', 'QuestionTranslation')

    for question in Question.objects.all():
        if question.question_text:
            # Create Kyrgyz translation from existing question_text
            QuestionTranslation.objects.get_or_create(
                question=question,
                language='ky',
                defaults={'text': question.question_text}
            )
            print(f"Migrated question {question.id}: {question.question_text[:50]}")


def reverse_migration(apps, schema_editor):
    """
    Reverse: Copy Kyrgyz translations back to question_text
    """
    Question = apps.get_model('chatbot', 'Question')
    QuestionTranslation = apps.get_model('chatbot', 'QuestionTranslation')

    for question in Question.objects.all():
        try:
            ky_translation = QuestionTranslation.objects.get(question=question, language='ky')
            question.question_text = ky_translation.text
            question.save()
        except QuestionTranslation.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0018_add_question_translation'),  # Update this to match your previous migration
    ]

    operations = [
        migrations.RunPython(migrate_questions_to_translations, reverse_migration),
    ]
