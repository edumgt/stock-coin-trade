package site.bitrun.cryptocurrency.global.api.coinmarketcap.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.CryptoRank;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.InnerQuote;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.domain.InnerUsd;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.dto.CryptoRankDto;
import site.bitrun.cryptocurrency.global.api.coinmarketcap.repository.CryptoRepository;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

@Service
public class CryptoServiceImpl implements CryptoService {

    private final CryptoRepository cryptoRepository;

    @Autowired
    public CryptoServiceImpl(CryptoRepository cryptoRepository) {
        this.cryptoRepository = cryptoRepository;
    }

    @Value("89a4ffe3-03a9-4184-87e0-49214b000b99")
    private String coinMarketCapApiKey;

    @Override
    public void saveCryptoRankList() {

        /**
         * 코인마켓캡 API > 시가총액순 TOP 100 코인 리스트 json parsing
         */
        String requestUrl = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?CMC_PRO_API_KEY=" + coinMarketCapApiKey;

        RestTemplate restTemplate = new RestTemplate();
        Map responseMap = restTemplate.getForObject(requestUrl, Map.class);
        Object data = responseMap.get("data"); // data 부분만 사용하기위해 가져옴

        ObjectMapper objectMapper = new ObjectMapper(); // Jackson lib
        objectMapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false); // dto 필드로 선언한 데이터만 파싱
        objectMapper.configure(MapperFeature.ACCEPT_CASE_INSENSITIVE_PROPERTIES, true); // 대소문자를 구분하지 않음

        String dataStr = null;
        try {
            dataStr = objectMapper.writeValueAsString(data); // json string 으로 형태 변환
        } catch (JsonProcessingException e) {
            throw new RuntimeException(e);
        }

        List<CryptoRankDto> cryptoRankDtos = null;
        try {
            CryptoRankDto[] cryptoRankDtosArray = objectMapper.readValue(dataStr, CryptoRankDto[].class);
            cryptoRankDtos = Arrays.asList(cryptoRankDtosArray);
        } catch (JsonProcessingException e) {
            throw new RuntimeException(e);
        }

        /**
         * 가공한 데이터 LIST DB INSERT (turncate 해준다)
         */
        cryptoRepository.truncateCryptoRankTable(); // 시가총액 top100 테이블 초기화

        List<CryptoRank> cryptoRanks = new ArrayList<>(); // rank data 담을 LIST

        for (CryptoRankDto cryptoRankDto : cryptoRankDtos) {

            CryptoRank cryptoRank = new CryptoRank();
            cryptoRank.setName(cryptoRankDto.getName());
            cryptoRank.setSymbol(cryptoRankDto.getSymbol());
            cryptoRank.setApiCryptoId(cryptoRankDto.getApiCryptoId());

            InnerUsd innerUsd = new InnerUsd();
            innerUsd.setPrice(cryptoRankDto.getQuote().getUsd().getPrice());
            innerUsd.setMarketCap(cryptoRankDto.getQuote().getUsd().getMarketCap());
            innerUsd.setPercentChange24h(cryptoRankDto.getQuote().getUsd().getPercentChange24h());
            innerUsd.setPercentChange7d(cryptoRankDto.getQuote().getUsd().getPercentChange7d());

            InnerQuote innerQuote = new InnerQuote();
            innerQuote.setUsd(innerUsd);
            cryptoRank.setQuote(innerQuote);

            cryptoRanks.add(cryptoRank);
        }

        cryptoRepository.saveAll(cryptoRanks);
    }

    @Override
    public List<CryptoRank> getCryptoRankList() {
        return cryptoRepository.findAll();
    }
}
