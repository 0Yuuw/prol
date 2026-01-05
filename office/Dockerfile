FROM tryton/tryton:7.6

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice-calc \
        libreoffice-draw \
        libreoffice-impress \
        libreoffice-writer \
        less \
        vim \
        wget \
        xvfb \
        nano \
        unzip \
        poppler-utils \
        zbar-tools \       
        libzbar0 && \          
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --break-system-packages \
        pdf2image \
        pyzbar \
        pillow \
        opencv-python \
        numpy \
        pdfminer.six



RUN chmod 777 /root && \
    chmod -R 777 /var/lib/trytond/www

USER trytond
