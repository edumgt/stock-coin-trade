package site.bitrun.cryptocurrency.controller.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

@RestController
public class StockApiProxyController {

    private static final MediaType JSON_UTF8 = new MediaType(MediaType.APPLICATION_JSON, StandardCharsets.UTF_8);
    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final String stockBackendBaseUrl;

    public StockApiProxyController(@Value("${stock.backend.base-url:http://localhost:8000}") String stockBackendBaseUrl) {
        this.stockBackendBaseUrl = stockBackendBaseUrl;
    }

    @GetMapping("/api/stocks/quote")
    public ResponseEntity<String> getQuote(@RequestParam("symbol") String symbol) {
        String encodedSymbol = URLEncoder.encode(symbol, StandardCharsets.UTF_8);
        return callBackend("GET", "/api/stocks/quote?symbol=" + encodedSymbol, null);
    }

    @GetMapping("/api/stocks/account")
    public ResponseEntity<String> getAccount() {
        return callBackend("GET", "/api/stocks/account", null);
    }

    @GetMapping("/api/stocks/positions")
    public ResponseEntity<String> getPositions() {
        return callBackend("GET", "/api/stocks/positions", null);
    }

    @PostMapping("/api/stocks/orders/buy")
    public ResponseEntity<String> buy(@RequestBody String body) {
        return callBackend("POST", "/api/stocks/orders/buy", body);
    }

    @PostMapping("/api/stocks/orders/sell")
    public ResponseEntity<String> sell(@RequestBody String body) {
        return callBackend("POST", "/api/stocks/orders/sell", body);
    }

    private ResponseEntity<String> callBackend(String method, String path, String requestBody) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(stockBackendBaseUrl + path))
                    .header("Content-Type", MediaType.APPLICATION_JSON_VALUE);

            if ("POST".equals(method)) {
                builder.POST(HttpRequest.BodyPublishers.ofString(requestBody == null ? "{}" : requestBody));
            } else {
                builder.GET();
            }

            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            return ResponseEntity
                    .status(response.statusCode())
                    .contentType(JSON_UTF8)
                    .body(response.body());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return ResponseEntity
                    .status(HttpStatus.SERVICE_UNAVAILABLE)
                    .contentType(JSON_UTF8)
                    .body("{\"error\":\"STOCK_BACKEND_INTERRUPTED\",\"message\":\"주식 실습 백엔드 호출이 중단되었습니다.\"}");
        } catch (IOException ex) {
            return ResponseEntity
                    .status(HttpStatus.SERVICE_UNAVAILABLE)
                    .contentType(JSON_UTF8)
                    .body("{\"error\":\"STOCK_BACKEND_UNAVAILABLE\",\"message\":\"주식 실습 백엔드 연결에 실패했습니다.\"}");
        }
    }
}
