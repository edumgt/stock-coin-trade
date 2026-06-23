package site.bitrun.cryptocurrency.controller.api;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.session.SessionConst;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/api/admin")
public class AdminApiController {

    private static final String ADMIN_EMAIL = "admin@admin.com";
    private static final MediaType JSON_UTF8 = new MediaType(MediaType.APPLICATION_JSON, StandardCharsets.UTF_8);

    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final String pythonBaseUrl;

    public AdminApiController(
            @Value("${stock.backend.base-url:http://localhost:8200}") String pythonBaseUrl) {
        this.pythonBaseUrl = pythonBaseUrl;
    }

    // ── 관리자 인증 체크 ──────────────────────────────────────────────────────
    private Member requireAdmin(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) return null;
        Member m = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);
        if (m == null || !ADMIN_EMAIL.equals(m.getEmail())) return null;
        return m;
    }

    // ── EKS 클러스터 현황 ─────────────────────────────────────────────────────
    @GetMapping("/k8s/overview")
    public ResponseEntity<String> k8sOverview(HttpServletRequest request) {
        if (requireAdmin(request) == null) return forbidden();
        return proxy("GET", "/api/admin/k8s/overview");
    }

    // ── 관리자 정보 (프론트 역할 확인용) ─────────────────────────────────────
    @GetMapping("/me")
    public ResponseEntity<String> adminMe(HttpServletRequest request) {
        Member m = requireAdmin(request);
        if (m == null) return forbidden();
        return ResponseEntity.ok()
                .contentType(JSON_UTF8)
                .body("{\"admin\":true,\"username\":\"" + m.getUsername() + "\"}");
    }

    // ── 내부 프록시 ──────────────────────────────────────────────────────────
    private ResponseEntity<String> proxy(String method, String path) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(pythonBaseUrl + path))
                    .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                    .GET()
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            return ResponseEntity.status(resp.statusCode()).contentType(JSON_UTF8).body(resp.body());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).contentType(JSON_UTF8)
                    .body("{\"error\":\"INTERRUPTED\"}");
        } catch (IOException ex) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).contentType(JSON_UTF8)
                    .body("{\"error\":\"PYTHON_BACKEND_UNAVAILABLE\"}");
        }
    }

    private ResponseEntity<String> forbidden() {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).contentType(JSON_UTF8)
                .body("{\"error\":\"관리자만 접근 가능합니다.\"}");
    }
}
