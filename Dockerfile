FROM python:3.9

RUN apt update && apt upgrade -y
RUN apt install python3-pip -y
RUN apt install ffmpeg -y
RUN apt install git -y

RUN curl -sL https://deb.nodesource.com/setup_16.x | bash -
RUN apt-get install -y nodejs
RUN npm i -g npm

RUN mkdir /VideoBot/
RUN git clone -b test https://github.com/Lost-In-Dark/VIDEO-PLAYER /VideoBot
WORKDIR /VideoBot

RUN pip3 install --upgrade pip
RUN pip3 install -U -r requirements.txt

CMD python3 -m vidstream.py
