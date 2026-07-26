package com.dermai.appointment;
import org.springframework.stereotype.Component;import org.springframework.transaction.support.*;
@Component class SlotUpdateBroadcaster{
 private final SlotWebSocketHandler handler;SlotUpdateBroadcaster(SlotWebSocketHandler handler){this.handler=handler;}
 void afterCommit(){afterCommit("SLOTS_CHANGED");}
 void chatChanged(){afterCommit("CHAT_CHANGED");}
 private void afterCommit(String type){if(TransactionSynchronizationManager.isSynchronizationActive())TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization(){@Override public void afterCommit(){handler.broadcast(type);}});else handler.broadcast(type);}
}
