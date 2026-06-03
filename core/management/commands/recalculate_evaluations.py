from django.core.management.base import BaseCommand
from core.models import OverallInternshipEvaluation

class Command(BaseCommand):
    help = 'Recalculate all overall evaluation scores and grades'

    def handle(self, *args, **options):
        evals = OverallInternshipEvaluation.objects.all()
        count = evals.count()
        self.stdout.write(f'Recalculating {count} evaluations...')
        
        updated = 0
        for evaluation in evals:
            old_grade = evaluation.final_grade
            old_score = evaluation.final_total_score
            evaluation.calculate_final()
            evaluation.save()
            if old_grade != evaluation.final_grade or old_score != evaluation.final_total_score:
                updated += 1
                self.stdout.write(f'Updated evaluation {evaluation.id}: {old_score} ({old_grade}) -> {evaluation.final_total_score} ({evaluation.final_grade})')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully recalculated {count} evaluations. {updated} records were changed.'))
