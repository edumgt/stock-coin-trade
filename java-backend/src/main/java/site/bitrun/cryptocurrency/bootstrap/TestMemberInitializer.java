package site.bitrun.cryptocurrency.bootstrap;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.repository.MemberRepository;

@Slf4j
@Component
public class TestMemberInitializer implements ApplicationRunner {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    public TestMemberInitializer(MemberRepository memberRepository, PasswordEncoder passwordEncoder) {
        this.memberRepository = memberRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(ApplicationArguments args) {
        createMemberIfNotExists("테스트회원1", "test1@test.com",  "123456",    10_000_000);
        createMemberIfNotExists("테스트회원2", "test2@test.com",  "123456",    10_000_000);
        createMemberIfNotExists("관리자",      "admin@admin.com", "admin1234", 999_999_999);
    }

    private void createMemberIfNotExists(String username, String email, String rawPassword, long asset) {
        if (memberRepository.findByEmail(email) != null) return;
        memberRepository.save(new Member(username, email, passwordEncoder.encode(rawPassword), asset));
        log.info("계정 생성: {} ({})", username, email);
    }
}
