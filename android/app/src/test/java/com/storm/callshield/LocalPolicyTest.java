package com.storm.callshield;
import static org.junit.Assert.*;

import org.junit.Test;
public class LocalPolicyTest {
  @Test
  public void whitelistWins() {
    assertEquals(LocalPolicy.Action.ALLOW, LocalPolicy.evaluate(true, true, 200, 100));
  }
  @Test
  public void spamRejects() {
    assertEquals(LocalPolicy.Action.REJECT, LocalPolicy.evaluate(false, true, 0, 100));
  }
  @Test
  public void suspiciousSilences() {
    assertEquals(LocalPolicy.Action.SILENCE, LocalPolicy.evaluate(false, false, 200, 100));
  }
  @Test
  public void expiryAllows() {
    assertEquals(LocalPolicy.Action.ALLOW, LocalPolicy.evaluate(false, false, 100, 100));
  }
  @Test
  public void unknownAllows() {
    assertEquals(LocalPolicy.Action.ALLOW, LocalPolicy.evaluate(false, false, 0, 100));
  }
  @Test
  public void wholeNumber() {
    assertEquals("+8613800000000", LocalPolicy.canonical("+86 138-0000-0000"));
  }
  @Test(expected = IllegalArgumentException.class)
  public void suffixRejected() {
    LocalPolicy.canonical("00000000");
  }
  @Test
  public void lowCannotWrite() {
    assertFalse(LocalPolicy.shouldWriteSuspicious(false, "suspicious", .2));
  }
  @Test
  public void whiteCannotPoison() {
    assertFalse(LocalPolicy.shouldWriteSuspicious(true, "suspicious", .9));
  }
  @Test
  public void noAutoSpam() {
    assertFalse(LocalPolicy.shouldWriteSuspicious(false, "spam", .99));
  }
}
