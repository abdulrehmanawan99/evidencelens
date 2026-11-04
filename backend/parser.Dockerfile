FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
RUN pip install --no-cache-dir pypdf==6.21.4
COPY app/pdf_parser.py /parser.py
RUN chmod 0444 /parser.py
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["python", "-I", "-B", "/parser.py"]
