package site.bitrun.cryptocurrency.controller;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.CryptoRank;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.dto.MemberLoginForm;
import site.bitrun.cryptocurrency.dto.MemberRegisterForm;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.service.CryptoService;
import site.bitrun.cryptocurrency.global.api.upbit.service.UpbitService;
import site.bitrun.cryptocurrency.service.MemberService;

import java.util.List;


@Controller
public class BasicController {

    private final MemberService memberService;
    private final CryptoService cryptoService;
    private final UpbitService upbitService;
    private final PasswordEncoder passwordEncoder;

    @Autowired
    public BasicController(MemberService memberService, CryptoService cryptoService, UpbitService upbitService, PasswordEncoder passwordEncoder) {
        this.memberService = memberService;
        this.cryptoService = cryptoService;
        this.upbitService = upbitService;
        this.passwordEncoder = passwordEncoder;
    }

    // 메인 페이지
    @GetMapping("/")
    public String main(Model model) {
        List<CryptoRank> cryptoRankList = cryptoService.getCryptoRankList();
        model.addAttribute("cryptoRankList", cryptoRankList);

        return "index";
    }

    // 주식 실습 화면
    @GetMapping("/trade/stock")
    public String stockPracticePage() {
        return "trade/stock";
    }

    // 회원가입 view
    @GetMapping("/member/register")
    public String memberRegisterForm(@ModelAttribute MemberRegisterForm memberRegisterForm) {
        return "member/memberRegisterForm";
    }

    // 회원가입
    @PostMapping("/member/register")
    public String memberRegister(@Validated @ModelAttribute MemberRegisterForm memberRegisterForm, BindingResult bindingResult, HttpServletRequest request) {

        if (bindingResult.hasErrors()) {
            return "member/memberRegisterForm";
        }

        // 비밀번호 확인
        if (!memberRegisterForm.getPassword().equals(memberRegisterForm.getPassword2())) {
            bindingResult.rejectValue("password2", "differentPassword", "패스워드가 일치하지 않습니다.");
            return "member/memberRegisterForm";
        }

        // 중복 체크
        // true 일 경우 중복
        if (memberService.memberCheckDuplicate(memberRegisterForm.getEmail())) {
            bindingResult.reject("emailDuplicate", "이미 존재하는 회원입니다."); // global error
            return "member/memberRegisterForm";
        }

        // 새로운 회원 가입
        String encodePassword = passwordEncoder.encode(memberRegisterForm.getPassword()); // 비밀번호 암호화
        Member newMember = new Member(memberRegisterForm.getUsername(), memberRegisterForm.getEmail(), encodePassword, 10000000);
        memberService.memberRegister(newMember);

        // 성공했다면 로그인까지 처리한다.
        memberService.memberLogin(memberRegisterForm.getEmail(), memberRegisterForm.getPassword(), request);

        return "redirect:/";
    }

    // 로그인 view
    @GetMapping("/member/login")
    public String memberLoginForm(@ModelAttribute MemberLoginForm memberLoginForm) {
        return "member/memberLoginForm";
    }

    // 로그인 처리
    @PostMapping("/member/login")
    public String memberLogin(@Validated @ModelAttribute MemberLoginForm memberLoginForm, BindingResult bindingResult, HttpServletRequest request) {

        if (bindingResult.hasErrors()) {
            return "member/memberLoginForm";
        }

        Member loginMember = memberService.memberLogin(memberLoginForm.getEmail(), memberLoginForm.getPassword(), request);

        // 로그인 실패시
        if (loginMember == null) {
            bindingResult.reject("loginFail", "아이디 또는 비밀번호가 맞지 않습니다."); // global error
            return "member/memberLoginForm";
        }

        return "redirect:/trade/order";
    }

    // 로그아웃
    @GetMapping("/member/logout")
    public String memberLogout(HttpServletRequest request) {
        memberService.memberLogout(request);

        return "redirect:/";
    }

}
