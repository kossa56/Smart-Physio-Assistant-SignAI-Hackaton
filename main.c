/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Smart Physio Assistant - B1 button, buzzer on PB2, data export
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "53l8a1_ranging_sensor.h"
#include "stdio.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef enum
{
  LOG,
  TRAINING,
} States_t;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define VERSION        150126u
#define TOF_SENSOR_ODR      3u /* Output Data Rate [Hz] */
#define RESULT_VALUES_NB    2u /* Logged result values: DISTANCE, SIGNAL */
#define TOF_RESOLUTION      VL53L8CX_RESOLUTION_8X8
#define SIGNAL_SIZE         (TOF_RESOLUTION * RESULT_VALUES_NB)
#define DISTANCE_MAX        2000u  /* [mm] */
#define SKIPPED_RESULTS_NB  2u     /* First ToF sensor results to be skipped */
#define LED_LOG_OK_PERIOD   75u    /* [ms] */
#define LED_LOG_NOK_PERIOD  25u

// Definicje dla liczenia powtórzeń
#define REP_THRESHOLD_MM    150.0f   /* Spadek odległości o 15 cm = ruch */
#define REP_TIMEOUT_MS      500      /* Min. czas między powtórzeniami [ms] */
#define BUZZER_DURATION_MS  100      /* Czas dźwięku buzzera [ms] */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */
/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */
RANGING_SENSOR_Capabilities_t Cap;
RANGING_SENSOR_ProfileConfig_t Profile;

__IO States_t appState = LOG;
__IO uint32_t ld2PeriodCnt = 0;
__IO uint32_t ld2Period = 0;
uint32_t resultCnt = 0;
float input_user_buffer[SIGNAL_SIZE] = {0};

// Zmienne dla sesji i powtórzeń
uint8_t sessionActive = 0;
uint32_t sessionStartTime = 0;
uint32_t repCount = 0;
uint32_t lastRepTime = 0;
float lastAvgDistance = 0.0f;

// Zmienna dla buzzera – czas do wyłączenia
uint32_t buzzerEndTime = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
void ToF_Init(void);
void ToF_ProfileConfig(uint8_t resolution);
void ToF_Start(void);
int32_t FillBuffer(float *buffer);
void PrintBuffer(float *buffer);
void Log(void);
float CalculateAverageDistance(void);
void HandleButton(void);
void PrintSessionInfo(void);
void BuzzerOn(void);
void BuzzerOff(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
int _write(int file, char *ptr, int len)
{
  HAL_UART_Transmit(&huart2, (uint8_t*)ptr, len, 100);
  return len;
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  HAL_Init();
  SystemClock_Config();

  MX_GPIO_Init();
  MX_USART2_UART_Init();

  /* USER CODE BEGIN 2 */
  printf("\r\nVer: %u.%u.%u\r\n", VERSION, SIGNAL_SIZE, TOF_SENSOR_ODR);

  ToF_Init();
  ToF_ProfileConfig(SIGNAL_SIZE);
  ToF_Start();

  // Nagłówek CSV – komentarz, nie będzie interpretowany jako dane
  printf("# timestamp_ms,distance_mm,session_time_s,repetition_count\r\n");

  printf("Press button B1 (blue) to start/stop session.\r\n");
  /* USER CODE END 2 */

  while (1)
  {
    /* USER CODE BEGIN 3 */
    // Wyłącz buzzera po upływie czasu
    if (buzzerEndTime && HAL_GetTick() >= buzzerEndTime)
    {
      BuzzerOff();
    }

    // Obsługa przycisku B1 (PC13) – odczyt stanu z debouncingiem
    if (HAL_GPIO_ReadPin(B1_GPIO_Port, B1_Pin) == GPIO_PIN_RESET)
    {
      HAL_Delay(50); // debouncing
      if (HAL_GPIO_ReadPin(B1_GPIO_Port, B1_Pin) == GPIO_PIN_RESET)
      {
        HandleButton();
        while(HAL_GPIO_ReadPin(B1_GPIO_Port, B1_Pin) == GPIO_PIN_RESET); // czekaj na puszczenie
      }
    }

    // Główna pętla stanu
    switch (appState)
    {
      case LOG:
        Log();
        break;
      default:
        appState = LOG;
        break;
    }

    // Co 2 sekundy wyświetlaj informacje o sesji
    static uint32_t lastPrint = 0;
    if ((HAL_GetTick() - lastPrint) > 2000)
    {
      lastPrint = HAL_GetTick();
      PrintSessionInfo();
    }
    /* USER CODE END 3 */
  }
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 10;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV7;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

void ToF_Init(void)
{
  int32_t status = 0;

  printf("ToF sensor init...\r\n");

  /* Sensor reset */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_RESET);
  HAL_Delay(2);
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_SET);
  HAL_Delay(2);
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_RESET);
  HAL_Delay(2);
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, GPIO_PIN_SET);
  HAL_Delay(2);

  status = VL53L8A1_RANGING_SENSOR_Init(VL53L8A1_DEV_CENTER);
  if (status != BSP_ERROR_NONE)
  {
    printf("ERROR\r\n");
    Error_Handler();
  }
  else
  {
    printf("OK\r\n");
  }
}

void ToF_ProfileConfig(uint8_t resolution)
{
  uint32_t Id;

  VL53L8A1_RANGING_SENSOR_ReadID(VL53L8A1_DEV_CENTER, &Id);
  VL53L8A1_RANGING_SENSOR_GetCapabilities(VL53L8A1_DEV_CENTER, &Cap);

  switch (resolution)
  {
    case VL53L8CX_RESOLUTION_8X8:
      Profile.RangingProfile = RS_PROFILE_8x8_CONTINUOUS;
      break;
    case VL53L8CX_RESOLUTION_4X4:
      Profile.RangingProfile = RS_PROFILE_4x4_CONTINUOUS;
      break;
    default:
      Profile.RangingProfile = RS_PROFILE_8x8_CONTINUOUS;
      break;
  }
  Profile.TimingBudget = 30; /* 5 ms < TimingBudget < 100 ms */
  Profile.Frequency = TOF_SENSOR_ODR; /* Hz */
  Profile.EnableSignal = 1;
  Profile.EnableAmbient = 0;

  VL53L8A1_RANGING_SENSOR_ConfigProfile(VL53L8A1_DEV_CENTER, &Profile);
  printf("ToF sensor ID: 0x%X\r\n", (int)Id);
}

void ToF_Start(void)
{
  int32_t status = 0;

  status = VL53L8A1_RANGING_SENSOR_Start(VL53L8A1_DEV_CENTER, RS_MODE_BLOCKING_CONTINUOUS);
  if (status != BSP_ERROR_NONE)
  {
    printf("ERROR: TOF sensor start failed\r\n");
    Error_Handler();
  }
}

int32_t FillBuffer(float *buffer)
{
  uint16_t i, j;
  RANGING_SENSOR_Result_t Result;
  int32_t status = 0;

  status = VL53L8A1_RANGING_SENSOR_GetDistance(VL53L8A1_DEV_CENTER, &Result);
  if (status == BSP_ERROR_NONE)
  {
    resultCnt++;
    j = 0;
    for (i = 0; i < TOF_RESOLUTION; i++)
    {
      if (Result.ZoneResult[i].Distance[0] <= DISTANCE_MAX)
      {
        buffer[j++] = (float)Result.ZoneResult[i].Distance[0];
      }
      else
      {
        buffer[j++] = DISTANCE_MAX;
      }
      buffer[j++] = (float)Result.ZoneResult[i].Signal[0];
    }
  }
  return status;
}

void PrintBuffer(float *buffer)
{
  uint16_t i = 0;

  while (i < SIGNAL_SIZE)
  {
    if (i < SIGNAL_SIZE - 1)
    {
      printf("%d ", (int)buffer[i]);
    }
    else
    {
      printf("%d\n", (int)buffer[i]);
    }
    i++;
  }
}

float CalculateAverageDistance(void)
{
  float sum = 0;
  int valid = 0;
  for (int i = 0; i < TOF_RESOLUTION; i++)
  {
    float dist = input_user_buffer[i * 2];
    if (dist > 0 && dist < DISTANCE_MAX)
    {
      sum += dist;
      valid++;
    }
  }
  return (valid > 0) ? (sum / valid) : 0.0f;
}

void Log(void)
{
  int32_t status = 0;
  status = FillBuffer(input_user_buffer);

  if (resultCnt > SKIPPED_RESULTS_NB)
  {
    if (status == 0)
    {
      ld2Period = LED_LOG_OK_PERIOD;

      if (sessionActive)
      {
        float avgDist = CalculateAverageDistance();
        uint32_t now = HAL_GetTick();
        uint32_t sessionTime = (now - sessionStartTime) / 1000; // sekundy

        // Wysyłanie danych CSV
        printf("%lu,%.1f,%lu,%lu\r\n", now, avgDist, sessionTime, repCount);

        // Wykrywanie powtórzeń (spadek odległości)
        if (lastAvgDistance > 0 && avgDist > 0 && (lastAvgDistance - avgDist) > REP_THRESHOLD_MM)
        {
          if ((now - lastRepTime) > REP_TIMEOUT_MS)
          {
            repCount++;
            lastRepTime = now;
            printf("Repetition %lu!\r\n", repCount);

            // Włącz buzzer
            BuzzerOn();
            // Mignięcie diodą LD2
            HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);
            HAL_Delay(50);
            HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_SET);
          }
        }
        lastAvgDistance = avgDist;
      }
    }
    else
    {
      ld2Period = LED_LOG_NOK_PERIOD;
    }
  }
  else
  {
    printf("Waiting for valid data... (resultCnt=%lu)\r\n", resultCnt);
  }
}

void HandleButton(void)
{
  if (!sessionActive)
  {
    // Rozpocznij sesję
    sessionActive = 1;
    sessionStartTime = HAL_GetTick();
    repCount = 0;
    lastRepTime = 0;
    lastAvgDistance = 0.0f;
    printf("\r\n*** SESJA ROZPOCZĘTA ***\r\n");
    ld2Period = LED_LOG_OK_PERIOD;
    ld2PeriodCnt = 0;
    // Krótki dźwięk potwierdzenia startu
    BuzzerOn();
    HAL_Delay(200);
    BuzzerOff();
  }
  else
  {
    // Zakończ sesję
    sessionActive = 0;
    printf("\r\n*** SESJA ZAKOŃCZONA ***\r\n");
    PrintSessionInfo();
    ld2Period = 0;
    HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);
    // Dwa krótkie dźwięki zakończenia
    for (int i = 0; i < 2; i++)
    {
      BuzzerOn();
      HAL_Delay(100);
      BuzzerOff();
      HAL_Delay(100);
    }
  }
}

void PrintSessionInfo(void)
{
  uint32_t elapsed = 0;
  if (sessionActive && sessionStartTime > 0)
  {
    elapsed = (HAL_GetTick() - sessionStartTime) / 1000;
  }
  uint32_t hours = elapsed / 3600;
  uint32_t minutes = (elapsed % 3600) / 60;
  uint32_t seconds = elapsed % 60;

  printf("[SESJA] Stan: %s | Czas: %02lu:%02lu:%02lu | Powtórzenia: %lu\r\n",
         sessionActive ? "AKTYWNA" : "NIEAKTYWNA",
         hours, minutes, seconds, repCount);
}

void BuzzerOn(void)
{
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_SET);
  buzzerEndTime = HAL_GetTick() + BUZZER_DURATION_MS;
}

void BuzzerOff(void)
{
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_RESET);
  buzzerEndTime = 0;
}

// Opcjonalne przerwanie od czujnika ToF (jeśli używane)
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin == GPIO_PIN_4)
  {
    // Nie używamy flagi, ale można zostawić puste
  }
}

void HAL_IncTick(void)
{
  uwTick += (uint32_t)uwTickFreq;
  if (ld2PeriodCnt > 0)
  {
    ld2PeriodCnt--;
  }
  else
  {
    if (ld2Period > 0)
    {
      ld2PeriodCnt = ld2Period;
      HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
    }
    else
    {
      HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);
    }
  }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  __disable_irq();
  while (1) {}
}

#ifdef  USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
