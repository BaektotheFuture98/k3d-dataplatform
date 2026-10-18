FROM python:3.12-slim-bookworm@sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163
RUN pip install --no-cache-dir boto3==1.40.59 botocore==1.40.59
USER 1000:1000
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/checks/s3-check.py"]
