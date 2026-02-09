FROM node:18-slim
WORKDIR /app
COPY discord-bots/starter-bot/package*.json ./
RUN npm install --omit=dev
COPY discord-bots/starter-bot/ .
CMD ["node", "src/bot.js"]
