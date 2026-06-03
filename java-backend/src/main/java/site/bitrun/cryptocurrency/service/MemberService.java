package site.bitrun.cryptocurrency.service;

import jakarta.servlet.http.HttpServletRequest;
import site.bitrun.cryptocurrency.domain.Member;

public interface MemberService {

    void memberRegister(Member member);

    boolean memberCheckDuplicate(String email);

    Member memberLogin(String email, String password, HttpServletRequest request);

    void memberLogout(HttpServletRequest request);

    Member getMemberInfo(long memberId);
}
