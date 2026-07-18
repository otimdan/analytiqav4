# Custom Analytika analysis sandbox.
#
# The default E2B code-interpreter image doesn't include statsmodels, which the
# VERIFIED regression path needs. This image preinstalls it so regression runs
# instantly (no per-session pip install). Until this is built + published, the
# regression templates self-install statsmodels once per sandbox as a fallback.
#
# Base: the E2B code-interpreter image the app already uses. If E2B changes the
# base tag, update it here (see https://e2b.dev/docs for the current base).
FROM e2bdev/code-interpreter:latest

# Pin statsmodels to match what the golden tests validate against.
RUN pip install --no-cache-dir statsmodels==0.14.6
