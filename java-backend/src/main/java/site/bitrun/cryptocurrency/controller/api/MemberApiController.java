package site.bitrun.cryptocurrency.controller.api;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.service.MemberService;
import site.bitrun.cryptocurrency.session.SessionConst;

import java.util.Map;

@RestController
@RequestMapping("/api/member")
public class MemberApiController {

    private final MemberService memberService;
    private final PasswordEncoder passwordEncoder;

    @Autowired
    public MemberApiController(MemberService memberService, PasswordEncoder passwordEncoder) {
        this.memberService = memberService;
        this.passwordEncoder = passwordEncoder;
    }

    @GetMapping("/me")
    public ResponseEntity<?> getCurrentUser(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) return ResponseEntity.ok(Map.of("loggedIn", false));
        Member loginMember = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);
        if (loginMember == null) return ResponseEntity.ok(Map.of("loggedIn", false));
        Member memberInfo = memberService.getMemberInfo(loginMember.getId());
        return ResponseEntity.ok(Map.of(
                "loggedIn", true,
                "username", memberInfo.getUsername(),
                "asset", memberInfo.getAsset()
        ));
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String email = body.get("email");
        String password = body.get("password");
        if (email == null || email.isBlank() || password == null || password.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "이메일과 비밀번호를 입력해주세요."));
        }
        Member loginMember = memberService.memberLogin(email, password, request);
        if (loginMember == null) {
            return ResponseEntity.status(401).body(Map.of("error", "아이디 또는 비밀번호가 맞지 않습니다."));
        }
        return ResponseEntity.ok(Map.of("username", loginMember.getUsername(), "asset", loginMember.getAsset()));
    }

    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String username = body.get("username");
        String email    = body.get("email");
        String password = body.get("password");
        String password2 = body.get("password2");

        if (username == null || username.isBlank())
            return ResponseEntity.badRequest().body(Map.of("field", "username", "error", "이름을 입력해주세요."));
        if (email == null || email.isBlank() || !email.contains("@"))
            return ResponseEntity.badRequest().body(Map.of("field", "email", "error", "올바른 이메일을 입력해주세요."));
        if (password == null || password.isBlank())
            return ResponseEntity.badRequest().body(Map.of("field", "password", "error", "비밀번호를 입력해주세요."));
        if (password2 == null || password2.isBlank())
            return ResponseEntity.badRequest().body(Map.of("field", "password2", "error", "비밀번호 확인을 입력해주세요."));
        if (!password.equals(password2))
            return ResponseEntity.badRequest().body(Map.of("field", "password2", "error", "패스워드가 일치하지 않습니다."));
        if (memberService.memberCheckDuplicate(email))
            return ResponseEntity.badRequest().body(Map.of("field", "email", "error", "이미 존재하는 회원입니다."));

        String encodePassword = passwordEncoder.encode(password);
        Member newMember = new Member(username, email, encodePassword, 10_000_000);
        memberService.memberRegister(newMember);
        memberService.memberLogin(email, password, request);

        return ResponseEntity.ok(Map.of("username", username));
    }

    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpServletRequest request) {
        memberService.memberLogout(request);
        return ResponseEntity.ok(Map.of("success", true));
    }
}
