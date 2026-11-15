FROM ros:jazzy-ros-base
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-slam-toolbox \
    python3-serial python3-smbus python3-flask python3-yaml python3-pil python3-pip python3-numpy \
    && pip3 install --break-system-packages pigpio==1.78 \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages waitress==3.0.2
WORKDIR /app
COPY . /app
CMD ["bash", "/app/start.sh"]
