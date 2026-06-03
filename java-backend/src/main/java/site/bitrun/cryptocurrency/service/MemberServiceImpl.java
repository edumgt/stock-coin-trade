package site.bitrun.cryptocurrency.service;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.repository.MemberRepository;
import site.bitrun.cryptocurrency.session.SessionConst;

@Service
public class MemberServiceImpl implements MemberService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    @Autowired
    public MemberServiceImpl(MemberRepository memberRepository, PasswordEncoder passwordEncoder) {
        this.memberRepository = memberRepository;
        this.passwordEncoder = passwordEncoder;
    }

    // 회원가입
    @Override
    public void memberRegister(Member member) {
        memberRepository.save(member);
    }

    // 로그인
    @Override
    public Member memberLogin(String email, String password, HttpServletRequest request) {
        Member findMember = memberRepository.findByEmail(email);

        if (findMember == null) {
            return null;
        }

        if ( passwordEncoder.matches(password, findMember.getPassword()) ) {
            HttpSession session = request.getSession();
            session.setAttribute(SessionConst.LOGIN_MEMBER, findMember);

            return findMember;
        } else {
            return null;
        }

    }

    // 로그아웃
    @Override
    public void memberLogout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);

        if (session != null) {
            session.invalidate();
        }
    }

    // 회원 중복체크
    @Override
    public boolean memberCheckDuplicate(String email) {
        Member checkMember = memberRepository.findByEmail(email);

        if (checkMember == null) {
            return false;
        }

        return true;
    }

    // 회원 정보 가져오기
    @Override
    public Member getMemberInfo(long memberId) {
        return memberRepository.findById(memberId);
    }

}
