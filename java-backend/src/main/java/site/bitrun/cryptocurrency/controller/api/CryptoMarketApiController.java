package site.bitrun.cryptocurrency.controller.api;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.CryptoRank;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.service.CryptoService;
import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;
import site.bitrun.cryptocurrency.global.api.upbit.service.UpbitService;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@RestController
public class CryptoMarketApiController {

    private final CryptoService cryptoService;
    private final UpbitService upbitService;

    @Autowired
    public CryptoMarketApiController(CryptoService cryptoService, UpbitService upbitService) {
        this.cryptoService = cryptoService;
        this.upbitService = upbitService;
    }

    @GetMapping("/api/crypto/rankings")
    public List<CryptoRank> getRankings() {
        return cryptoService.getCryptoRankList();
    }

    @GetMapping("/api/crypto/market-list")
    public Map<String, Object> getMarketList() {
        List<UpbitMarket> markets = upbitService.getUpbitMarketList();
        List<String> marketCodes = new ArrayList<>();
        for (UpbitMarket m : markets) {
            marketCodes.add(m.getMarket());
        }
        return Map.of("markets", markets, "marketCodes", marketCodes);
    }
}
