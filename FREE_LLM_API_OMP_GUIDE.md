# omp 可串接的免費 LLM API 評估

## 結論

以 omp 程式開發代理的用途評估：

- **整體最推薦：Google Gemini API**：準確度、長上下文、多模態與效能最均衡。
- **速度最推薦：Groq API**：延遲低，適合互動式 coding agent。
- **隱私最推薦：Ollama 本機 API**：不需要雲端 API 額度，程式碼可留在本機。
- **多模型切換最推薦：OpenRouter**：一個 API 可切換多個免費模型，但供應狀態與品質較不固定。

以下以「適合 omp 程式開發代理」評估，權重約為**準確度 60%、效能／延遲 40%**。星等是實務評估，不是官方 benchmark 排名；實際結果仍取決於模型、提示詞、上下文長度與工具呼叫能力。

## 一、嚴格免費或有固定免費層的排序

| 排名 | API／omp provider | 建議模型 | 準確度 | 效能 | 免費條件 |
|---:|---|---|---:|---:|---|
| 1 | Google Gemini，`google` | `gemini-3.8-flash` 或 `gemini-3.6-flash` | ★★★★★ | ★★★★☆ | 特定模型提供免費輸入／輸出額度 |
| 2 | Groq，`groq` | `openai/gpt-oss-120b` | ★★★★☆ | ★★★★★ | 免費層有 RPM、RPD、TPM、TPD 限制 |
| 3 | OpenRouter，`openrouter` | 任一 `:free` 模型 | ★★★★☆～★★★☆☆ | ★★★☆☆ | 免費模型；無付費額度時約 20 RPM、50 RPD |
| 4 | Mistral，`mistral` | `mistral-small-latest` | ★★★★☆ | ★★★☆☆ | Free mode；不需信用卡，但有月額與速率限制 |
| 5 | Ollama，`ollama` | `gpt-oss:20b`、`qwen3:8b` 等 | ★★★☆☆～★★★★☆ | 依硬體 | 本機免費；成本轉移到本機 CPU／GPU／記憶體 |

### 1. Google Gemini API：整體第一名

**適合：**需要較高準確度、複雜程式分析、長上下文、圖片或文件理解。

#### 特色

- Gemini Flash 系列在速度、程式理解與長上下文之間平衡良好。
- 支援文字與多模態輸入，適合讀取架構圖、截圖與文件內容。
- omp 有內建 `google` provider，不需要自行寫 `models.yml`。
- Google 官方免費層提供部分模型的免費輸入與輸出 token。

#### 弱點

- 免費層的 RPM、TPM、RPD 不是固定公開值，必須到 Google AI Studio 查看目前專案的實際限制。
- 免費層送出的內容可能被 Google 用於改善產品；**不要送密碼、token、私人 Wi-Fi 設定或未公開原始碼**。
- 服務端速率限制可能因模型、專案與帳戶狀態變動。
- Preview／experimental 模型的穩定性較低。

官方文件：

- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

### 2. Groq API：速度第一名

**適合：**需要即時回應、頻繁修改程式與互動式 terminal coding。

#### 特色

- Groq 使用專用推論硬體；官方模型頁列出 `openai/gpt-oss-120b` 約 **500 tokens/s** 的速度。
- `gpt-oss-120b` 具備推理與 agentic coding 能力，品質高於一般小型模型。
- OpenAI-compatible，omp 直接支援 `groq`。
- 對 omp 這種需要多輪工具呼叫的程式代理，低延遲很有感。

#### 弱點

- 免費層的 token 額度不大。官方文件列出的 `gpt-oss-120b` 免費限制約為：
  - 30 RPM
  - 1,000 RPD
  - 8K TPM
  - 200K TPD
- 高峰或大量並行時容易遇到 HTTP 429。
- 速度快不代表模型一定比 Gemini 準確；品質取決於選用的模型。
- Groq 的模型與 API 政策可能變動，Preview 模型不適合作為長期固定依賴。

官方文件：

- [Groq Supported Models](https://console.groq.com/docs/models)
- [Groq Rate Limits](https://console.groq.com/docs/rate-limits)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)

### 3. OpenRouter：模型選擇最多

**適合：**想比較不同免費模型，或希望未來快速更換模型供應商。

#### 特色

- 一個 API 介面可使用多家模型與供應商。
- 以 `:free` 後綴選擇免費模型。
- 可根據模型品質、速度、上下文或供應商狀態切換。
- 對 omp 而言，OpenRouter 是方便的 fallback provider。

#### 弱點

- 免費模型不是固定清單，會變動、下架或暫時無可用 provider。
- 同一個模型可能因實際路由到不同供應商而產生不同延遲與穩定性。
- 沒有付費額度時，官方文件列出的限制約為 20 RPM、50 RPD。
- 使用至少 10 美元額度後，免費模型的 RPD 上限可提高到約 1,000；這已不是嚴格的零付費方案。
- 免費模型常有較嚴格的上下文、輸出長度或工具呼叫限制。

官方文件：

- [OpenRouter Free model variant](https://openrouter.ai/docs/guides/routing/model-variants/free)
- [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits)

### 4. Mistral API：直接、穩定、限制清楚

**適合：**希望使用直接模型 API，不想經過 aggregator，且能接受中等速度與額度。

#### 特色

- Mistral Free mode 可建立 API key，官方說明不需要信用卡。
- 直接連到 Mistral API，路由層較少，行為較容易預測。
- `mistral-small-latest` 適合一般程式說明、重構建議與文件生成。
- omp 有內建 `mistral` provider。

#### 弱點

- 免費模式的模型、月額、TPM、RPS 依組織與帳戶顯示，不是所有帳戶都有同一組數值。
- 複雜 agentic coding 的穩定度與工具使用能力通常不如較大型 reasoning model。
- 速度通常不如 Groq。
- 超過免費月額後會停止或需要付費額度。

官方文件：

- [Mistral free mode API key](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key)
- [Mistral usage and limits](https://docs.mistral.ai/admin/billing-usage/usage-limits)

### 5. Ollama：本機免費 API

**適合：**私人程式碼、離線工作、教學環境與沒有雲端 API 額度的情境。

#### 特色

- API 在本機執行，不需要雲端 API key。
- omp 會自動探索本機 Ollama。
- 支援 OpenAI-compatible `/v1/chat/completions` 與 `/v1/responses`。
- 程式碼不必送到第三方雲端，隱私最佳。
- 可依硬體選擇模型大小，例如：
  - `qwen3:8b`：較省資源。
  - `gpt-oss:20b`：品質與資源需求折衷。
  - 更大型模型：品質可能更好，但需要較多 VRAM／RAM。

#### 弱點

- 效能完全取決於本機硬體。
- 沒有足夠 VRAM 時，模型可能非常慢。
- 小模型在大型重構、跨檔案推理、工具呼叫與錯誤修正方面，通常不如雲端大型模型。
- 需要自行下載模型與管理本機磁碟、記憶體、更新。

官方文件：

- [omp local provider documentation](https://omp.sh/docs/providers)
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)

## 二、只有試用額度，不算永久免費

### Cerebras API

Cerebras 的推論速度很有吸引力，且 `gpt-oss-120b` 適合程式代理；但目前官方明確說明：

- 新帳戶需加入已驗證的付款方式。
- 提供 **5 美元試用額度**。
- 額度取得後 30 天過期。
- 沒有永久自動更新的免費層。
- Free Trial 的 `gpt-oss-120b` 約為 5 RPM、30K uncached TPM、1M TPD。

因此它可以測試，但不應視為長期免費方案。

官方文件：

- [Cerebras rate limits and Free Trial](https://inference-docs.cerebras.ai/support/rate-limits)

## 三、其他可透過自訂路由使用的方案

### Cloudflare Workers AI

Cloudflare Workers AI 提供每日 **10,000 Neurons** 的免費配置，模型包括 Llama、Qwen、GPT-OSS、Gemma 等。

但要注意：

- omp 內建的是 `cloudflare-ai-gateway`，不是直接的 `cloudflare-workers-ai` provider。
- 若要使用，通常要透過 Cloudflare AI Gateway、OpenAI-compatible gateway 或自訂 provider。
- 部分較新的模型需要付費 Workers plan 或預付額度。
- 因此不如 Gemini、Groq、Ollama 直接。

官方文件：

- [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)

### Hugging Face Inference Providers

目前免費帳戶沒有固定的免費 Inference Providers 額度；官方表格顯示：

- Free users：沒有每月免費 credits。
- PRO：每月 2 美元 credits。
- Team／Enterprise：每席每月 2 美元 credits。

因此不應把 Hugging Face API 當成一般免費 API 推薦，除非已有 PRO、Team 或 Enterprise 資格。

官方文件：

- [Hugging Face Inference Providers pricing](https://huggingface.co/docs/inference-providers/en/pricing)

## 四、在 omp 中的設定方式

omp 已內建這些 provider：

```text
google
groq
mistral
openrouter
cerebras
ollama
```

官方文件：

- [omp Providers](https://omp.sh/docs/providers)
- [omp Environment variables](https://omp.sh/docs/env)

### Google Gemini

PowerShell：

```powershell
$env:GEMINI_API_KEY = "你的 Gemini API key"

omp models google
omp --model google/<從 omp models 顯示的實際模型 ID>
```

例如模型清單確實包含該模型時：

```powershell
omp --model google/gemini-3.8-flash
```

### Groq

```powershell
$env:GROQ_API_KEY = "你的 Groq API key"

omp models groq
omp --model groq/openai/gpt-oss-120b
```

### OpenRouter

```powershell
$env:OPENROUTER_API_KEY = "你的 OpenRouter API key"

omp models openrouter
omp --model openrouter/<免費模型 ID>:free
```

OpenRouter 的免費模型清單會變動，應以 `omp models openrouter` 顯示的實際 ID 為準。

### Mistral

```powershell
$env:MISTRAL_API_KEY = "你的 Mistral API key"

omp models mistral
omp --model mistral/mistral-small-latest
```

### Ollama

先啟動 Ollama 並下載模型：

```powershell
ollama pull gpt-oss:20b
omp models ollama
omp --model ollama/gpt-oss:20b
```

Ollama 本機通常不需要 API key。若 omp 要求欄位，使用任意非秘密值即可；本機 Ollama 會忽略該值。

## 五、實際建議

### 一般教學與程式開發

```text
主要：Google Gemini Flash
備援：Groq gpt-oss-120b
本機隱私：Ollama gpt-oss:20b 或 qwen3
```

### 想要最快互動速度

```text
主要：Groq
備援：Gemini Flash
```

### 需要處理私人原始碼或學生資料

```text
主要：Ollama 本機模型
備援：已確認資料政策的付費／企業 API
```

### 想比較多個免費模型

```text
主要：OpenRouter :free
備援：Gemini 或 Groq
```

### 最保守的 omp 配置

建議配置兩至三個 provider，而不是只依賴一個：

```text
slow / high-quality：Google Gemini
fast / interactive：Groq
local / private：Ollama
```

API key 應放在 `.env` 或系統環境變數，不要放進 Git、`models.yml` 明文、課程投影片或公開 repository。

## 六、限制與時效性

- 免費方案、模型 ID、速率限制與資料政策會變動；使用前應執行 `omp models <provider>`，並查看供應商最新文件。
- `omp models` 顯示的可用模型優先於本文件的範例模型名稱。
- 本文件比較的是 API／模型組合，不是只比較供應商品牌；同一供應商換模型後，準確度與效能可能完全不同。
- 未執行本機硬體 benchmark，也未對各 API 做同一批程式題目的實測；排名屬於基於官方能力、免費限制與 omp 整合便利性的工程評估。
