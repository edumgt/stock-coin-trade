package site.bitrun.cryptocurrency.controller.api;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import site.bitrun.cryptocurrency.domain.HoldCrypto;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.dto.HoldCryptoDto;
import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;
import site.bitrun.cryptocurrency.global.api.upbit.service.UpbitService;
import site.bitrun.cryptocurrency.repository.HoldCryptoRepository;
import site.bitrun.cryptocurrency.service.HoldCryptoService;
import site.bitrun.cryptocurrency.service.MemberService;
import site.bitrun.cryptocurrency.session.SessionConst;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/trade")
public class TradeApiController {

    private final UpbitService upbitService;
    private final HoldCryptoService holdCryptoService;
    private final MemberService memberService;
    private final HoldCryptoRepository holdCryptoRepository;

    @Autowired
    public TradeApiController(UpbitService upbitService, HoldCryptoService holdCryptoService,
                              MemberService memberService, HoldCryptoRepository holdCryptoRepository) {
        this.upbitService = upbitService;
        this.holdCryptoService = holdCryptoService;
        this.memberService = memberService;
        this.holdCryptoRepository = holdCryptoRepository;
    }

    @GetMapping("/hold")
    public ResponseEntity<?> getHoldCrypto(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Member loginMember = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);
        Member memberInfo = memberService.getMemberInfo(loginMember.getId());

        List<HoldCryptoDto> holdCryptoList = holdCryptoService.getHoldCryptoList(loginMember.getId());
        long totalBuyKrw = 0;
        List<String> marketArrayList = new ArrayList<>();
        for (HoldCryptoDto h : holdCryptoList) {
            totalBuyKrw += h.getBuyTotalKrw();
            marketArrayList.add(h.getMarketCode());
        }

        return ResponseEntity.ok(Map.of(
                "memberAsset", memberInfo.getAsset(),
                "totalBuyKrw", totalBuyKrw,
                "holdCryptoList", holdCryptoList,
                "marketArrayList", marketArrayList
        ));
    }

    @PostMapping("/order/buy")
    public ResponseEntity<?> buyCrypto(@RequestBody Map<String, String> body, HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Member loginMember = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);

        String marketCode = body.get("marketCode");
        String buyKrwStr  = body.get("buyKrw");
        if (marketCode == null || buyKrwStr == null)
            return ResponseEntity.badRequest().body(Map.of("error", "마켓코드와 매수금액을 입력해주세요."));

        Long buyKrw;
        try {
            buyKrw = Long.parseLong(buyKrwStr.replaceAll(",", ""));
        } catch (Exception ex) {
            return ResponseEntity.badRequest().body(Map.of("error", "숫자만 입력해주세요."));
        }
        if (buyKrw <= 0)
            return ResponseEntity.badRequest().body(Map.of("error", "0보다 큰 수를 입력해주세요."));

        Member memberInfo = memberService.getMemberInfo(loginMember.getId());
        if (buyKrw > memberInfo.getAsset())
            return ResponseEntity.badRequest().body(Map.of("error", "매수 가능 금액보다 클 수 없습니다."));

        holdCryptoService.buyCrypto(loginMember.getId(), marketCode, buyKrw);
        Member updated = memberService.getMemberInfo(loginMember.getId());
        return ResponseEntity.ok(Map.of("success", true, "asset", updated.getAsset()));
    }

    @PostMapping("/order/sell")
    public ResponseEntity<?> sellCrypto(@RequestBody Map<String, String> body, HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Member loginMember = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);

        String marketCode  = body.get("marketCode");
        String sellCountStr = body.get("sellCount");
        if (marketCode == null || sellCountStr == null)
            return ResponseEntity.badRequest().body(Map.of("error", "마켓코드와 매도수량을 입력해주세요."));

        Double sellCount;
        try {
            sellCount = Double.parseDouble(sellCountStr);
        } catch (Exception ex) {
            return ResponseEntity.badRequest().body(Map.of("error", "숫자만 입력해주세요."));
        }
        if (sellCount <= 0)
            return ResponseEntity.badRequest().body(Map.of("error", "0보다 큰 수를 입력해주세요."));

        UpbitMarket market = upbitService.getUpbitMarketOne(marketCode);
        HoldCrypto held = holdCryptoRepository.findByMemberIdAndUpbitMarketId(loginMember.getId(), market.getId());
        if (held == null)
            return ResponseEntity.badRequest().body(Map.of("error", "암호화폐를 보유중이지 않습니다."));
        if (held.getBuyCryptoCount() < sellCount)
            return ResponseEntity.badRequest().body(Map.of("error", "매도 가능 개수보다 클 수 없습니다."));

        holdCryptoService.sellCrypto(loginMember.getId(), marketCode, sellCount);
        Member updated = memberService.getMemberInfo(loginMember.getId());
        return ResponseEntity.ok(Map.of("success", true, "asset", updated.getAsset()));
    }
}
