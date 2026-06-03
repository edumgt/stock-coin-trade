package site.bitrun.cryptocurrency.service;

import site.bitrun.cryptocurrency.domain.HoldCrypto;
import site.bitrun.cryptocurrency.dto.HoldCryptoDto;

import java.util.List;

public interface HoldCryptoService {

    void buyCrypto(long memberId, String marketCode, long buyKrw); // 매수

     void sellCrypto(long memberId, String marketCode, double sellCryptoCount); // 매도

    List<HoldCryptoDto> getHoldCryptoList(long memberId); // 보유 암호화폐 list

}
