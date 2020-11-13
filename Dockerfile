FROM python:3.8-slim-buster
LABEL org.opencontainers.image.source https://github.com/FrozenChen/Mayushii
ENV IS_DOCKER=1
ENV PYTHONUNBUFFERED=1
ENV HOME /home/mayushii
RUN useradd -m -d $HOME -s /bin/sh -u 3198 mayushii
WORKDIR $HOME
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
USER mayushii
#ARG BRANCH="unknown"
#ENV COMMIT_BRANCH=${BRANCH}
#ARG COMMIT="unknown"
#ENV COMMIT_SHA=${COMMIT}
COPY --chown=3198:3198 . .
CMD ["python3", "main.py"]
