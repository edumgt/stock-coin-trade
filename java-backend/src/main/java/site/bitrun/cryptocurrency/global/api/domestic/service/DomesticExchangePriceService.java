package site.bitrun.cryptocurrency.global.api.domestic.service;

import site.bitrun.cryptocurrency.global.api.domestic.dto.DomesticExchangePriceResponseDto;

public interface DomesticExchangePriceService {

    DomesticExchangePriceResponseDto getDomesticPrices(String marketCode);
}
