package site.bitrun.cryptocurrency.controller.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.http.ResponseEntity;

import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@RestController
@RequestMapping("/api/ai")
public class AiAnalysisController {

    private final String apiKey;
    private final HttpClient httpClient = HttpClient.newHttpClient();

    public AiAnalysisController(@Value("${anthropic.api-key:}") String apiKey) {
        this.apiKey = apiKey;
    }

    @PostMapping(value = "/analyze", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public ResponseEntity<StreamingResponseBody> analyze(@RequestBody Map<String, String> body) {
        String context = body.getOrDefault("context", "시세 데이터 없음");
        String type    = body.getOrDefault("type", "general");

        String systemPrompt = "당신은 한국 금융 시장 전문가입니다. 제공된 실시간 시세 데이터를 분석하여 한국어로 명확하고 실용적인 투자 조언을 제공합니다. " +
                "이 내용은 투자 교육 목적이며, 실제 투자 결정은 본인 판단에 따라야 함을 고지합니다.";

        String userPrompt = buildPrompt(type, context);

        if (apiKey == null || apiKey.isBlank()) {
            StreamingResponseBody fallback = out -> {
                String msg = "⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.\n\n환경변수 ANTHROPIC_API_KEY를 설정하면 AI 분석이 활성화됩니다.";
                out.write(msg.getBytes(StandardCharsets.UTF_8));
                out.flush();
            };
            return ResponseEntity.ok().contentType(MediaType.TEXT_EVENT_STREAM).body(fallback);
        }

        String requestBody = String.format("""
            {
              "model": "claude-haiku-4-5-20251001",
              "max_tokens": 1024,
              "stream": true,
              "system": "%s",
              "messages": [{"role": "user", "content": "%s"}]
            }""",
            escapeJson(systemPrompt),
            escapeJson(userPrompt)
        );

        StreamingResponseBody stream = out -> {
            try {
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create("https://api.anthropic.com/v1/messages"))
                        .header("Content-Type", "application/json")
                        .header("x-api-key", apiKey)
                        .header("anthropic-version", "2023-06-01")
                        .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                        .build();

                HttpResponse<InputStream> response = httpClient.send(request,
                        HttpResponse.BodyHandlers.ofInputStream());

                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (line.startsWith("data: ")) {
                            String data = line.substring(6).trim();
                            if (data.equals("[DONE]")) break;
                            if (data.contains("\"text\"")) {
                                int start = data.indexOf("\"text\":\"") + 8;
                                int end   = data.lastIndexOf("\"");
                                if (start > 8 && end > start) {
                                    String text = data.substring(start, end)
                                            .replace("\\n", "\n")
                                            .replace("\\\"", "\"");
                                    out.write(text.getBytes(StandardCharsets.UTF_8));
                                    out.flush();
                                }
                            }
                        }
                    }
                }
            } catch (Exception e) {
                String err = "\n\n⚠️ AI 분석 중 오류가 발생했습니다: " + e.getMessage();
                out.write(err.getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        };

        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .body(stream);
    }

    private String buildPrompt(String type, String context) {
        String label = switch (type) {
            case "crypto" -> "코인 시장";
            case "stock"  -> "주식 시장";
            default       -> "전체 금융 시장";
        };
        return String.format(
            "다음은 현재 %s의 실시간 시세 데이터입니다:\n\n%s\n\n" +
            "위 데이터를 바탕으로 다음을 분석해주세요:\n" +
            "1. 시장 전반적인 분위기와 트렌드\n" +
            "2. 주목할 만한 종목이나 코인과 그 이유\n" +
            "3. 단기 관점에서의 유의 사항\n" +
            "4. 리스크 관리 조언\n\n" +
            "간결하고 실용적으로 답변해주세요. (교육 목적)",
            label, context
        );
    }

    private String escapeJson(String s) {
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
