class CodexWriterError(Exception):
    code = "CODEX_WRITER_ERROR"
    exit_code = 1

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class PathOutsideProject(CodexWriterError):
    code = "PATH_OUTSIDE_PROJECT"
    exit_code = 2


class LockAlreadyHeld(CodexWriterError):
    code = "LOCK_ALREADY_HELD"
    exit_code = 6


class AtomicWriteError(CodexWriterError):
    code = "ATOMIC_WRITE_ERROR"
    exit_code = 6


class SchemaValidationFailed(CodexWriterError):
    code = "SCHEMA_VALIDATION_FAILED"
    exit_code = 2


class ChapterBriefMissing(CodexWriterError):
    code = "CHAPTER_BRIEF_MISSING"
    exit_code = 3


class StoryContractMissing(CodexWriterError):
    code = "STORY_CONTRACT_MISSING"
    exit_code = 3


class ReviewResultMissing(CodexWriterError):
    code = "REVIEW_RESULT_MISSING"
    exit_code = 3


class ExtractionResultMissing(CodexWriterError):
    code = "EXTRACTION_RESULT_MISSING"
    exit_code = 3


class PlaceholderFound(CodexWriterError):
    code = "PLACEHOLDER_FOUND"
    exit_code = 3


class ProviderFailure(CodexWriterError):
    code = "PROVIDER_FAILURE"
    exit_code = 5


class PrivacyBlock(CodexWriterError):
    code = "PRIVACY_BLOCK"
    exit_code = 4


class MigrationMissing(CodexWriterError):
    code = "MIGRATION_MISSING"
    exit_code = 7


class MigrationsNotInitialized(CodexWriterError):
    code = "MIGRATIONS_NOT_INITIALIZED"
    exit_code = 7
