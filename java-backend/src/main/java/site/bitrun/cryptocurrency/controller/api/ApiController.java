package site.bitrun.cryptocurrency.controller.api;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import site.bitrun.cryptocurrency.domain.HoldCrypto;
import site.bitrun.cryptocurrency.domain.Member;
import site.bitrun.cryptocurrency.global.api.domestic.dto.DomesticExchangePriceResponseDto;
import site.bitrun.cryptocurrency.global.api.domestic.service.DomesticExchangePriceService;
import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;
import site.bitrun.cryptocurrency.global.api.upbit.service.UpbitService;
import site.bitrun.cryptocurrency.repository.HoldCryptoRepository;
import site.bitrun.cryptocurrency.service.HoldCryptoService;
import site.bitrun.cryptocurrency.session.SessionConst;

@RestController
public class ApiController {

    private final UpbitService upbitService;
    private final HoldCryptoService holdCryptoService;
    private final HoldCryptoRepository holdCryptoRepository;
    private final DomesticExchangePriceService domesticExchangePriceService;

    @Autowired
    public ApiController(UpbitService upbitService, HoldCryptoService holdCryptoService,
                         HoldCryptoRepository holdCryptoRepository, DomesticExchangePriceService domesticExchangePriceService) {
        this.upbitService = upbitService;
        this.holdCryptoService = holdCryptoService;
        this.holdCryptoRepository = holdCryptoRepository;
        this.domesticExchangePriceService = domesticExchangePriceService;
    }

    // 거래소 개별 암호화폐 정보 API
    @GetMapping("/api/crypto/{code}")
    public UpbitMarketApiDto getCryptoInfo(@PathVariable("code") String code, HttpServletRequest request) {

        // 쿼리 파라미터로 해당하는 암호화폐의 정보를 1개 가져온다.
        UpbitMarket findUpbitCryptoOne = upbitService.getUpbitMarketOne(code);
        double buyCryptoCount = 0;

        // 로그인 유저 체크 - 로그인시 매도 가능 금액 넘겨주기 위함
        HttpSession session = request.getSession(false);
        if (session != null) {
            Member loginMember = (Member) session.getAttribute(SessionConst.LOGIN_MEMBER);

            if (loginMember != null) {
                Long findCryptoId = findUpbitCryptoOne.getId(); // 암호화폐 고유 id
                
                HoldCrypto findHoldCryptoOne 
                = holdCryptoRepository.findByMemberIdAndUpbitMarketId(loginMember.getId(), findCryptoId);

                // 매수한 암호화폐 정보가 있으면 넣어준다
                if (findHoldCryptoOne != null) {
                    buyCryptoCount = findHoldCryptoOne.getBuyCryptoCount();
                }
            }

        }

        UpbitMarketApiDto result = new UpbitMarketApiDto(findUpbitCryptoOne.getMarket(), findUpbitCryptoOne.getKoreanName(), findUpbitCryptoOne.getEnglishName(), buyCryptoCount);

        return result;
    }

    // 거래소 개별 암호화폐 국내 4대 거래소 시세 API
    @GetMapping("/api/crypto/{code}/domestic-prices")
    public DomesticExchangePriceResponseDto getDomesticExchangePrices(@PathVariable("code") String code) {
        return domesticExchangePriceService.getDomesticPrices(code);
    }

    static class UpbitMarketApiDto {
        String marketCode;
        String koreanName;
        String englishName;
        double buyCryptoCount;

        public UpbitMarketApiDto(String marketCode, String koreanName, String englishName, double buyCryptoCount) {
            this.marketCode = marketCode;
            this.koreanName = koreanName;
            this.englishName = englishName;
            this.buyCryptoCount = buyCryptoCount;
        }

        public String getMarketCode() {
            return marketCode;
        }

        public void setMarketCode(String marketCode) {
            this.marketCode = marketCode;
        }

        public String getKoreanName() {
            return koreanName;
        }

        public void setKoreanName(String koreanName) {
            this.koreanName = koreanName;
        }

        public String getEnglishName() {
            return englishName;
        }

        public void setEnglishName(String englishName) {
            this.englishName = englishName;
        }

        public double getBuyCryptoCount() {
            return buyCryptoCount;
        }

        public void setBuyCryptoCount(double buyCryptoCount) {
            this.buyCryptoCount = buyCryptoCount;
        }
    }

}
