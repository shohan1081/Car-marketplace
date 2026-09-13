"""
Auto-fails AIVideoGeneration jobs that have been stuck in 'processing' for
too long.

This exists because the whole pipeline depends on a single webhook call from
the external car-video-agent service to ever move a job out of 'processing'.
If that call is ever silently lost (an unhandled exception in the agent's
background task, a rejected webhook due to a misconfigured token, a network
blip, the agent container restarting mid-job), Django has no way to notice --
the row just sits there forever with no error surfaced to the dealer.

Run this periodically (e.g. every 10 minutes via cron/systemd timer) so a
config or infra problem shows up as a failed job within minutes instead of
requiring someone to notice a dealer complaint and dig through logs by hand.

Example crontab entry on the host:
    */10 * * * * cd /home/ubuntu/nory-backend && docker compose exec -T web python manage.py fail_stale_ai_videos
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from vehicles.models import AIVideoGeneration

# Real jobs finish in a few minutes (fal.ai Kling generation has taken ~5
# minutes in observed runs). 20 minutes gives generous headroom before
# assuming something went wrong, without making dealers wait an hour to find
# out a job failed.
DEFAULT_STALE_MINUTES = 20


class Command(BaseCommand):
    help = "Marks AIVideoGeneration jobs stuck in 'processing' past a timeout as 'failed'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=DEFAULT_STALE_MINUTES,
            help=f"Age in minutes after which a still-'processing' job is considered stale (default: {DEFAULT_STALE_MINUTES}).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="List the jobs that would be failed without changing them.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options['minutes'])
        stale = AIVideoGeneration.objects.filter(status='processing', created_at__lt=cutoff)

        count = stale.count()
        if count == 0:
            self.stdout.write("No stale AI video generation jobs found.")
            return

        if options['dry_run']:
            for job in stale:
                self.stdout.write(f"Would fail: job_id={job.job_id} dealer={job.dealer.email} created_at={job.created_at}")
            self.stdout.write(self.style.WARNING(f"{count} stale job(s) found (dry run, nothing changed)."))
            return

        stale.update(
            status='failed',
            error_message=(
                "No result was received from the AI video generation service in time. "
                "This usually means the webhook delivery failed (check the agent's "
                "BACKEND_WEBHOOK_URL token) or the agent process restarted mid-job. "
                "Please try generating again."
            ),
        )
        self.stdout.write(self.style.SUCCESS(f"Marked {count} stale AI video generation job(s) as failed."))
