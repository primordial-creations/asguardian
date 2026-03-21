from typing import List, Tuple

from Asgard.Volundr.Scaffold.models.scaffold_models import (
    FileEntry,
    ServiceConfig,
)


def typescript_package_json(config: ServiceConfig) -> str:
    return f'''{{
  "name": "{config.name}",
  "version": "0.1.0",
  "description": "{config.description}",
  "main": "dist/index.js",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node-dev --respawn src/index.ts",
    "test": "jest",
    "lint": "eslint src --ext .ts"
  }},
  "dependencies": {{
    "express": "^4.18.0",
    "dotenv": "^16.3.0"
  }},
  "devDependencies": {{
    "@types/express": "^4.17.0",
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "ts-node-dev": "^2.0.0"
  }}
}}
'''


def typescript_tsconfig(config: ServiceConfig) -> str:
    return '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
'''


def typescript_index(config: ServiceConfig) -> str:
    return f'''import express from 'express';
import {{ config }} from './config';
import {{ healthRouter }} from './routes/health';

const app = express();

app.use(express.json());
app.use('/health', healthRouter);

app.get('/', (req, res) => {{
  res.json({{ message: 'Welcome to {config.name}' }});
}});

app.listen(config.port, () => {{
  console.log(`Server running on port ${{config.port}}`);
}});
'''


def typescript_config(config: ServiceConfig) -> str:
    return f'''import dotenv from 'dotenv';

dotenv.config();

export const config = {{
  port: parseInt(process.env.PORT || '{config.port}', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
}};
'''


def typescript_health_route(config: ServiceConfig) -> str:
    return '''import { Router } from 'express';

export const healthRouter = Router();

healthRouter.get('/', (req, res) => {
  res.json({ status: 'healthy' });
});

healthRouter.get('/ready', (req, res) => {
  res.json({ status: 'ready' });
});

healthRouter.get('/live', (req, res) => {
  res.json({ status: 'alive' });
});
'''


def typescript_dockerfile(config: ServiceConfig) -> str:
    return f'''FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

USER appuser

EXPOSE {config.port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD node -e "require('http').get('http://localhost:{config.port}/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "dist/index.js"]
'''


def generate_typescript_service(config: ServiceConfig) -> Tuple[List[FileEntry], List[str]]:
    files: List[FileEntry] = []
    directories: List[str] = [
        f"{config.name}",
        f"{config.name}/src",
        f"{config.name}/src/routes",
        f"{config.name}/src/services",
        f"{config.name}/src/models",
        f"{config.name}/src/config",
    ]

    if config.include_tests:
        directories.append(f"{config.name}/tests")

    files.append(FileEntry(
        path=f"{config.name}/package.json",
        content=typescript_package_json(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/tsconfig.json",
        content=typescript_tsconfig(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/src/index.ts",
        content=typescript_index(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/src/config/index.ts",
        content=typescript_config(config),
    ))

    if config.include_healthcheck:
        files.append(FileEntry(
            path=f"{config.name}/src/routes/health.ts",
            content=typescript_health_route(config),
        ))

    if config.include_docker:
        files.append(FileEntry(
            path=f"{config.name}/Dockerfile",
            content=typescript_dockerfile(config),
        ))

    return files, directories


def go_mod(config: ServiceConfig) -> str:
    return f'''module {config.name}

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
)
'''


def go_main(config: ServiceConfig) -> str:
    return f'''package main

import (
    "log"
    "{config.name}/internal/config"
    "{config.name}/internal/handlers"
    "github.com/gin-gonic/gin"
)

func main() {{
    cfg := config.Load()

    r := gin.Default()

    // Health routes
    r.GET("/health", handlers.HealthCheck)
    r.GET("/health/ready", handlers.ReadinessCheck)
    r.GET("/health/live", handlers.LivenessCheck)

    // Root route
    r.GET("/", func(c *gin.Context) {{
        c.JSON(200, gin.H{{"message": "Welcome to {config.name}"}})
    }})

    log.Printf("Starting server on port %d", cfg.Port)
    if err := r.Run(fmt.Sprintf(":%d", cfg.Port)); err != nil {{
        log.Fatal(err)
    }}
}}
'''


def go_config(config: ServiceConfig) -> str:
    return f'''package config

import (
    "os"
    "strconv"
)

type Config struct {{
    Port int
    Env  string
}}

func Load() *Config {{
    port := {config.port}
    if p := os.Getenv("PORT"); p != "" {{
        if parsed, err := strconv.Atoi(p); err == nil {{
            port = parsed
        }}
    }}

    return &Config{{
        Port: port,
        Env:  getEnv("ENV", "development"),
    }}
}}

func getEnv(key, defaultValue string) string {{
    if value := os.Getenv(key); value != "" {{
        return value
    }}
    return defaultValue
}}
'''


def go_health_handler(config: ServiceConfig) -> str:
    return '''package handlers

import (
    "github.com/gin-gonic/gin"
)

func HealthCheck(c *gin.Context) {
    c.JSON(200, gin.H{"status": "healthy"})
}

func ReadinessCheck(c *gin.Context) {
    c.JSON(200, gin.H{"status": "ready"})
}

func LivenessCheck(c *gin.Context) {
    c.JSON(200, gin.H{"status": "alive"})
}
'''


def go_dockerfile(config: ServiceConfig) -> str:
    return f'''FROM golang:1.21-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o server ./cmd/server

FROM gcr.io/distroless/static-debian12

COPY --from=builder /app/server /server

EXPOSE {config.port}

USER nonroot:nonroot

ENTRYPOINT ["/server"]
'''


def generate_go_service(config: ServiceConfig) -> Tuple[List[FileEntry], List[str]]:
    files: List[FileEntry] = []
    directories: List[str] = [
        f"{config.name}",
        f"{config.name}/cmd",
        f"{config.name}/cmd/server",
        f"{config.name}/internal",
        f"{config.name}/internal/handlers",
        f"{config.name}/internal/services",
        f"{config.name}/internal/config",
        f"{config.name}/pkg",
    ]

    if config.include_tests:
        directories.append(f"{config.name}/internal/handlers")

    files.append(FileEntry(path=f"{config.name}/go.mod", content=go_mod(config)))
    files.append(FileEntry(
        path=f"{config.name}/cmd/server/main.go",
        content=go_main(config),
    ))
    files.append(FileEntry(
        path=f"{config.name}/internal/config/config.go",
        content=go_config(config),
    ))

    if config.include_healthcheck:
        files.append(FileEntry(
            path=f"{config.name}/internal/handlers/health.go",
            content=go_health_handler(config),
        ))

    if config.include_docker:
        files.append(FileEntry(
            path=f"{config.name}/Dockerfile",
            content=go_dockerfile(config),
        ))

    return files, directories
