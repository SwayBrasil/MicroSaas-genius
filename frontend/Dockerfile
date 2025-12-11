FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN npm install
COPY . .
RUN npm run build || yarn build || pnpm build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app /app
EXPOSE 3000
CMD ["npm","run","preview","--","--host","0.0.0.0","--port","3000"]
