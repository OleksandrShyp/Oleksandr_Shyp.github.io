int UY = 0;      //Premenné na uchovávanie hodnôt z analógových vstupov
int UX = 0; 
#include "LedControl.h" // Knižnica na ovládanie LED matice
#include <TimerMs.h>    // Knižnica na časovanie

LedControl lc=LedControl(13,11,12,1); //Inicializuje maticu LED s piny 13, 11, 12
TimerMs displayData(300, 1, 0);     // inicializuje časovač s periódou 300 ms

void setup() {
  Serial.begin(9600);    // Inicializuje sériovú komunikáciu s rýchlosťou 9600 bps
 
  lc.shutdown(0,false);     // Zapne maticu
  lc.setIntensity(0,8);    // Nastaví jas matice 
  lc.clearDisplay(0);      // Clear display

}

void loop() {
    UX = analogRead(A4);     // Analógové hodnoty z pinov A4 a A5
    UY = analogRead(A5);

  char x = map(UX, 1021, 0, 7, 0);  //Mapujú hodnoty z rozsahu 0-1021 na rozsah 0-7
  char y = map(UY, 1021, 0, 0, 7);



  if(displayData.tick()){    //  Kontroluje, či časovač uplynul (300 ms). 
  //Ak áno, vypíše hodnoty UX, UY a pozície x, y na sériový port
  Serial.print("UX = ");
  Serial.print(UX, DEC);
   Serial.print(", UY = ");
  Serial.print(UY, DEC);
  Serial.print(", y = ");
 Serial.print(x+1, DEC);
  Serial.print(", x = ");
  Serial.println(y+1, DEC);}
 
    lc.clearDisplay(0);      //// Clear display
    lc.setLed(0,x,y,true);  //  Nastaví LED na pozíciu (x, y) na zapnutú (true)
}