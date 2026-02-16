FROM alpine:3.19
RUN apk add --no-cache openssh-client autossh
ENTRYPOINT ["autossh", "-M", "0", "-N", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3", "-L", "0.0.0.0:5432:localhost:5432"]
