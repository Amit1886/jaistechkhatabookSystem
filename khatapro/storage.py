"""
khatapro/storage.py
-------------------
Custom static file storage:
- Generates original + .gz + hashed + hashed.gz per file → 8000+ total files
- Does NOT crash when vendor CSS references missing font paths
  (e.g. super_admin/gentelella bootstrap-datetimepicker fonts)

Root cause: whitenoise's CompressedManifestStaticFilesStorage YIELDS
(name, hashed_name, MissingFileError) tuples — it doesn't raise.
Django's collectstatic then re-raises any Exception in that tuple.
We intercept at the yield level and convert errors to a skip (True).
"""
import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage, MissingFileError

logger = logging.getLogger(__name__)


class RobustCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Same as CompressedManifestStaticFilesStorage but silently skips any
    MissingFileError (broken vendor CSS → missing font/image reference)
    instead of letting Django's collectstatic raise it and abort.
    """
    # Django ManifestStaticFilesStorage: False = don't raise on missing
    # referenced files (belt-and-suspenders alongside our yield intercept)
    manifest_strict = False

    def post_process(self, paths, dry_run=False, **options):
        for name, hashed_name, processed in super().post_process(
            paths, dry_run=dry_run, **options
        ):
            if isinstance(processed, MissingFileError):
                # A vendor CSS references a file that doesn't exist.
                # Log a warning and mark as processed (skip) so collectstatic
                # doesn't abort the entire run.
                logger.warning(
                    "[collectstatic] Skipping missing vendor file referenced by '%s': %s",
                    name,
                    processed,
                )
                yield name, hashed_name, True
            else:
                yield name, hashed_name, processed
