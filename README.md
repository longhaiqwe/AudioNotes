# AudioNotes

## 支持云端 Groq 与本地 FunASR/Ollama 的音视频转结构化笔记系统

能够快速提取音视频的内容，使用 LLM 对转录文稿进行轻度润色（修正口误、补全标点、分段），再整理成结构化的 Markdown 笔记，方便快速阅读。

- **云端模式（默认）**
  - ASR：Groq Whisper API（`whisper-large-v3`）
  - LLM：Groq Chat API（`qwen/qwen3-32b`）
- **本地模式**
  - ASR：FunASR（`paraformer-zh`）
  - LLM：Ollama OpenAI-compatible API（默认 `qwen2:7b`）
- **网页内切换**
  - 在 Chainlit 页面右上角设置中选择 ASR 引擎和 LLM 引擎
  - 同一套服务内可在 Groq 和本地模式之间切换
- **处理流程**
  1. 音视频文件上传 → ASR 转录
  2. LLM 润色文稿（修正口误、补标点、分段，保留原意）
  3. LLM 整理为结构化笔记
  4. 可继续对话，就笔记内容提问

Groq Cloud: https://console.groq.com
FunASR: https://github.com/modelscope/FunASR
Ollama: https://ollama.com

## 效果展示

### 音视频识别和整理

![image](docs/1.jpg)

### 与音视频内容对话

![image](docs/2.jpg)

## 使用方法

### ① 准备环境变量

复制 `.env.example` 为 `.env`，并配置登录、数据库和模型服务。

启动服务后，可以在网页右上角设置中选择 ASR 引擎和 LLM 引擎。环境变量中的 `ASR_PROVIDER` / `LLM_PROVIDER` 只是默认值。

云端 Groq 模式需要前往 https://console.groq.com/keys 创建 API Key，并配置：

```bash
ASR_PROVIDER=groq
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
```

本地模式需要先安装并启动 Ollama，然后拉取模型：

```bash
ollama pull qwen2:7b
```

本地模式可在网页设置中选择 `FunASR（本地）` 和 `Ollama（本地）`。如果希望默认进入本地模式，可配置：

```bash
ASR_PROVIDER=funasr
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2:7b
OLLAMA_API_KEY=ollama
```

### ② 部署服务

推荐使用 Docker 部署。当前镜像已内置 Groq、FunASR、Ollama 客户端所需依赖，启动后可在网页设置中切换云端或本地模式。

#### 统一镜像启动

```bash
docker compose up --build
```
Docker 启动后，访问 http://localhost:15433/，在页面右上角设置中选择：

- ASR 引擎：`Groq Whisper（云端）` 或 `FunASR（本地）`
- LLM 引擎：`Groq LLM（云端）` 或 `Ollama（本地）`

> 登录账号为 admin，密码为 admin （可以在 docker-compose.yml 文件里面修改）

#### 数据持久化

Docker Compose 已配置以下 volume 挂载，数据保存在项目目录下，重建容器不会丢失：

| 宿主机路径 | 容器路径 | 用途 |
|---|---|---|
| `./storage` | `/app/storage` | 上传的音视频文件 |
| `./modelscope_cache` | `/root/.cache/modelscope` | FunASR 模型缓存（首次约 1GB，之后免下载） |
| `./postgresql` | `/var/lib/postgresql/data` | PostgreSQL 数据库 |

> 首次使用 FunASR 时会从 ModelScope 下载模型，需要容器能访问外网。下载完成后模型缓存在本地，后续重建容器无需重新下载。

#### 本地 FunASR + Ollama 默认模式

如果希望容器启动后默认选择本地模式，可以叠加本地 compose：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

Docker 容器内访问宿主机 Ollama 默认使用：

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
```

#### 非 Docker 本地部署 📦

需要有可访问的 PostgreSQL 数据库，以及系统安装 `ffmpeg`（用于音频分片）。

```bash
conda create -n AudioNotes python=3.10 -y
conda activate AudioNotes
git clone https://github.com/harry0703/AudioNotes.git
cd AudioNotes
pip install -r requirements.txt
```

将 `.env.example` 重命名为 `.env`，修改相关配置信息

```bash
chainlit run main.py
```
服务启动后，访问 http://localhost:8000/

> 登录账号为 admin，密码为 admin （可以在 .env 文件里面修改）
