#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Prioriza venv sobre sistema
venv_site = [p for p in sys.path if 'site-packages' in p and '/venv/' in p]
system_site = [p for p in sys.path if '/usr/lib/python3/dist-packages' in p]
other_paths = [p for p in sys.path if p not in venv_site and p not in system_site]

sys.path = venv_site + other_paths + system_site

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
import time
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ===== CONFIGURACIÓN =====
SHEET_NAME = os.getenv("SHEET_NAME", "Consultas RUNT")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
RUNT_URL = os.getenv(
    "RUNT_URL",
    "https://portalpublico.runt.gov.co/#/consulta-vehiculo/consulta/consulta-ciudadana",
)
DEBUG_DIR = os.getenv("DEBUG_DIR", "debug")
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes", "si", "sí")
ENABLE_GROQ_CAPTCHA = os.getenv("ENABLE_GROQ_CAPTCHA", "false").lower() in (
    "1",
    "true",
    "yes",
    "si",
    "sí",
)


def debug_path(filename):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    return os.path.join(DEBUG_DIR, filename)


# ===== Screens =====
class RuntScreen:
    placa_input = (By.CSS_SELECTOR, "input[formcontrolname='placa']")
    tipo_doc_select = (By.CSS_SELECTOR, "mat-select[formcontrolname='tipoDocumento']")
    cedula_input = (By.CSS_SELECTOR, "input[formcontrolname='documento']")
    captcha_input = (By.CSS_SELECTOR, "input[formcontrolname='captcha']")
    submit_btn = (By.CSS_SELECTOR, "button[type='submit']")

# ===== Actions =====
class EnterText:
    @staticmethod
    def into(driver, text, locator):
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(locator)
            )
            element.clear()
            element.send_keys(text)
            time.sleep(0.5)
            return True
        except:
            return False

class ClickOn:
    @staticmethod
    def element(driver, locator):
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(locator)
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            try:
                element.click()
            except:
                driver.execute_script("arguments[0].click();", element)
            return True
        except:
            return False

class SelectOption:
    @staticmethod
    def cedula_ciudadania(driver, locator):
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(locator)
            )
            driver.execute_script("arguments[0].click();", element)
            time.sleep(1.5)
            
            try:
                option = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Cédula Ciudadanía')]"))
                )
                driver.execute_script("arguments[0].click();", option)
                time.sleep(0.5)
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(0.5)
            except:
                element.send_keys(Keys.ESCAPE)
                time.sleep(0.5)
            return True
        except:
            return False

class ExtractData:
    @staticmethod
    def get_soat_vigente(driver):
        try:
            print("  🛡️  Buscando SOAT...")
            time.sleep(5)
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)
            
            try:
                panel_soat = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//mat-panel-title[contains(text(), 'SOAT')]"))
                )
            except:
                panel_soat = driver.find_element(By.XPATH, "//*[contains(text(), 'Póliza SOAT') or contains(text(), 'SOAT')]")
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", panel_soat)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", panel_soat)
            print("  ✅ Panel SOAT abierto")
            time.sleep(4)
            
            filas = driver.find_elements(By.CSS_SELECTOR, "tr")
            
            for fila in filas:
                texto = fila.text.upper()
                if "VIGENTE" in texto and "NO VIGENTE" not in texto:
                    celdas = fila.find_elements(By.CSS_SELECTOR, "td")
                    if len(celdas) >= 6:
                        datos = {
                            'soat_numero': celdas[0].text.strip(),
                            'soat_expedicion': celdas[1].text.strip(),
                            'soat_inicio': celdas[2].text.strip(),
                            'soat_fin': celdas[3].text.strip(),
                            'soat_aseguradora': celdas[4].text.strip(),
                            'soat_estado': 'VIGENTE'
                        }
                        print(f"  ✅ SOAT vigente hasta: {datos['soat_fin']}")
                        return datos
            
            print("  ⚠️  No hay SOAT vigente")
            return {'soat_numero': '', 'soat_expedicion': '', 'soat_inicio': '', 'soat_fin': '', 'soat_aseguradora': '', 'soat_estado': 'NO VIGENTE'}
            
        except Exception as e:
            print(f"  ⚠️  SOAT error: {str(e)[:80]}")
            return {'soat_numero': '', 'soat_expedicion': '', 'soat_inicio': '', 'soat_fin': '', 'soat_aseguradora': '', 'soat_estado': 'ERROR'}
    
    @staticmethod
    def get_rtm_vigente(driver):
        try:
            print("  🔧 Buscando RTM...")
            driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(2)
            
            try:
                panel_rtm = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//mat-panel-title[contains(text(), 'técnico mecánica')]"))
                )
            except:
                panel_rtm = driver.find_element(By.XPATH, "//*[contains(text(), 'Certificado de revisión') or contains(text(), 'RTM')]")
            
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", panel_rtm)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", panel_rtm)
            print("  ✅ Panel RTM abierto")
            time.sleep(4)
            
            filas = driver.find_elements(By.CSS_SELECTOR, "tr")
            
            for fila in filas:
                celdas = fila.find_elements(By.CSS_SELECTOR, "td")
                if len(celdas) >= 6:
                    vigente = celdas[4].text.strip().upper() if len(celdas) > 4 else ""
                    if vigente == "SI":
                        datos = {
                            'rtm_numero': celdas[5].text.strip() if len(celdas) > 5 else '',
                            'rtm_vigencia': celdas[2].text.strip() if len(celdas) > 2 else '',
                            'rtm_cda': celdas[3].text.strip() if len(celdas) > 3 else '',
                            'rtm_estado': 'VIGENTE'
                        }
                        print(f"  ✅ RTM vigente hasta: {datos['rtm_vigencia']}")
                        return datos
            
            print("  ⚠️  No hay RTM vigente")
            return {'rtm_numero': '', 'rtm_vigencia': '', 'rtm_cda': '', 'rtm_estado': 'NO VIGENTE'}
            
        except Exception as e:
            print(f"  ⚠️  RTM error: {str(e)[:80]}")
            return {'rtm_numero': '', 'rtm_vigencia': '', 'rtm_cda': '', 'rtm_estado': 'ERROR'}

# ===== Tasks =====
class ConsultarRuntTask:
    def __init__(self, driver, placa, cedula):
        self.driver = driver
        self.placa = placa.upper().strip()
        self.cedula = str(cedula).strip()

    def resolver_captcha_con_groq(self):
        """Resuelve CAPTCHA usando Groq Vision API con reintentos"""
        if not ENABLE_GROQ_CAPTCHA:
            print("  ⌨️  CAPTCHA manual configurado")
            return self.resolver_captcha_gratis()

        intentos_maximos = 5
        
        for intento in range(1, intentos_maximos + 1):
            try:
                import sys
                import importlib.util
                
                spec = importlib.util.find_spec("groq")
                if spec is None:
                    print("  ⚠️  Groq no instalado, usando OCR local")
                    return self.resolver_captcha_gratis()
                
                from groq import Groq
                import base64
                from dotenv import load_dotenv
                import os
                
                load_dotenv()
                api_key = os.getenv('GROQ_API_KEY')
                
                if not api_key:
                    print("  ⚠️  GROQ_API_KEY no encontrada")
                    return self.resolver_captcha_gratis()
                
                    # Toma screenshot del CAPTCHA - Método mejorado
                try:
                    # Intenta capturar el contenedor completo del CAPTCHA
                    captcha_container = self.driver.find_element(By.CSS_SELECTOR, "img[src^='data:image/png']")
                    
                    # Toma screenshot con margen extra
                    location = captcha_container.location
                    size = captcha_container.size
                    
                    # Screenshot de toda la página
                    pagina_completa = debug_path('pagina_completa.png')
                    self.driver.save_screenshot(pagina_completa)
                    print(f"  📸 Screenshot página completa: {pagina_completa}")
                    
                    # Recorta el área del CAPTCHA con margen
                    from PIL import Image
                    img = Image.open(pagina_completa)
                    
                    left = max(0, location['x'] - 10)
                    top = max(0, location['y'] - 10)
                    right = location['x'] + size['width'] + 10
                    bottom = location['y'] + size['height'] + 10
                    
                    captcha_img = img.crop((left, top, right, bottom))
                    captcha_temp = debug_path('captcha_temp.png')
                    captcha_img.save(captcha_temp)
                    print(f"  ✂️  CAPTCHA recortado: {captcha_temp}")
                    
                except Exception as e:
                    print(f"  ⚠️  Error capturando: {e}")
                    # Fallback: screenshot del elemento directamente
                    captcha_img = self.driver.find_element(By.CSS_SELECTOR, "img[src^='data:image/png']")
                    captcha_img.screenshot(debug_path('captcha_temp.png'))
                
                # Amplia la imagen 3x (sin distorsión)
                from PIL import Image
                img = Image.open(debug_path('captcha_temp.png'))
                img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
                captcha_final = debug_path('captcha_final.png')
                img.save(captcha_final)
                print(f"  🔍 CAPTCHA final ampliado: {captcha_final}")
                
                # Convierte a base64
                with open(captcha_final, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')


                
                # Llama a Groq Vision con prompt mejorado
                print(f"  🤖 Groq Vision (intento {intento}/{intentos_maximos})...")
                client = Groq(api_key=api_key)
                
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a CAPTCHA reader. Return ONLY the characters you see, nothing else."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_data}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": """Look at this CAPTCHA image. You will see 4-7 distorted alphanumeric characters.

YOUR TASK: Extract ONLY those characters in exact order from left to right.

RULES:
- Return ONLY the characters (A-Z, a-z, 0-9)
- NO explanations, NO sentences, NO descriptions
- NO "The image shows", NO "The text is"
- ONLY the raw characters

CORRECT examples:
✓ HRuu3
✓ Pk5bK
✓ amkSi

WRONG examples:
✗ The image shows the text HRuu3
✗ I see: HRuu3
✗ The characters are HRuu3

Characters:"""
                                }
                            ]
                        }
                    ],
                    temperature=0.0,
                    max_tokens=8
                )
                
                captcha_text = response.choices[0].message.content.strip()
                captcha_text = captcha_text.replace(" ", "").replace("\n", "")
                captcha_text = re.sub(r'[^a-zA-Z0-9]', '', captcha_text)
                
                print(f"  ✅ Groq detectó: '{captcha_text}' (len: {len(captcha_text)})")

                
                # Validación (acepta 4-7 caracteres)
                if 4 <= len(captcha_text) <= 7:
                    print(f"  🚀 Usando: {captcha_text}")
                    EnterText.into(self.driver, captcha_text, RuntScreen.captcha_input)
                    time.sleep(1)
                    return True
                else:
                    print(f"  ⚠️  Longitud incorrecta ({len(captcha_text)} chars, esperado 4-7)")
                    if intento < intentos_maximos:
                        print("  🔄 Reintentando...")
                        time.sleep(2)
                        continue
                    else:
                        print("  👁️  Verifica manualmente")
                        captcha_manual = input("  ⌨️  CAPTCHA (ENTER=usar sugerencia): ").strip()
                        captcha_final = captcha_manual if captcha_manual else captcha_text
                        EnterText.into(self.driver, captcha_final, RuntScreen.captcha_input)
                        time.sleep(1)
                        return True
                
            except ImportError as e:
                print(f"  ⚠️  Import error: {str(e)[:50]}")
                return self.resolver_captcha_gratis()
            except Exception as e:
                print(f"  ⚠️  Error Groq: {str(e)[:80]}")
                if intento < intentos_maximos:
                    print("  🔄 Reintentando...")
                    time.sleep(2)
                    continue
                else:
                    print("  🔄 Usando OCR local como fallback")
                    return self.resolver_captcha_gratis()
        
        return self.resolver_captcha_gratis()
    

    def resolver_captcha_gratis(self):
        """Permite resolver el CAPTCHA manualmente sin depender de servicios externos."""
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            self.driver.save_screenshot(debug_path("captcha_page.png"))
            captcha_img = self.driver.find_element(By.CSS_SELECTOR, "img[src^='data:image/png']")
            captcha_file = debug_path("captcha_manual.png")
            captcha_img.screenshot(captcha_file)
            print(f"  👁️  CAPTCHA guardado en: {captcha_file}")
        except Exception as e:
            print(f"  ⚠️  No se pudo guardar imagen del CAPTCHA: {str(e)[:80]}")

        captcha_manual = input("  ⌨️  Escribe el CAPTCHA y presiona ENTER: ").strip()
        if not captcha_manual:
            return False

        EnterText.into(self.driver, captcha_manual, RuntScreen.captcha_input)
        time.sleep(1)
        return True

    
    
    def extraer_datos_completos(self):
        driver = self.driver
        
        print("  ⏳ Esperando carga de resultados...")
        time.sleep(1)
        
        print("  📄 Extrayendo datos del vehículo con Groq Vision...")
        
        try:
            from groq import Groq
            import base64
            from dotenv import load_dotenv
            import os
            import json
            
            load_dotenv()
            api_key = os.getenv('GROQ_API_KEY')
            client = Groq(api_key=api_key)
            
            # ========== EXTRAE DATOS DEL VEHÍCULO ==========
            # 🔥 SCROLL ARRIBA ANTES DEL SCREENSHOT
           # ========== EXTRAE DATOS DEL VEHÍCULO ==========
            print("  📜 Scroll arriba (tecla HOME)...")
            from selenium.webdriver.common.keys import Keys
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.HOME)
            time.sleep(3)

            paso1_vehiculo = debug_path('paso1_vehiculo.png')
            driver.save_screenshot(paso1_vehiculo)
            with open(paso1_vehiculo, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            
            print("  🤖 Groq: Extrayendo datos del vehículo...")
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "system",
                    "content": "Extract vehicle data. Return ONLY JSON."
                }, {
                    "role": "user",
                    "content": [{
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"}
                    }, {
                        "type": "text",
                        "text": """Extract vehicle info from "Información general del vehículo" section.

    Return ONLY this JSON:
    {
    "marca": "",
    "linea": "",
    "modelo": "",
    "color": "",
    "combustible": "",
    "clase": "",
    "tipo_servicio": "",
    "estado": ""
    }"""
                    }]
                }],
                temperature=0.1,
                max_tokens=200
            )
            
            respuesta = str(response.choices[0].message.content).strip()
            json_str = respuesta[respuesta.find("{"):respuesta.rfind("}")+1]
            datos_vehiculo = json.loads(json_str)
            print(f"  ✅ Vehículo: {datos_vehiculo.get('marca')} {datos_vehiculo.get('linea')} {datos_vehiculo.get('modelo')}")
            
            # ========== EXTRAE SOAT ==========
            print("  🛡️  Abriendo panel SOAT...")
            driver.execute_script("window.scrollTo(0, 600);")
            time.sleep(2)
            
            try:
                # Busca y abre el panel SOAT
                panel_soat = driver.find_element(By.XPATH, "//mat-expansion-panel-header[.//mat-panel-title[contains(text(), 'SOAT')]]")
                driver.execute_script("arguments[0].scrollIntoView(true);", panel_soat)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", panel_soat)
                time.sleep(4)
                print("  ✅ Panel SOAT abierto")
                
                # Screenshot solo del panel SOAT
                paso2_soat = debug_path('paso2_soat.png')
                driver.save_screenshot(paso2_soat)
                with open(paso2_soat, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                print("  🤖 Groq: Extrayendo SOAT...")
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "system",
                        "content": "Extract SOAT data from table. Return ONLY JSON."
                    }, {
                        "role": "user",
                        "content": [{
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }, {
                            "type": "text",
                            "text": """Find the "Póliza SOAT" table. Extract ONLY the FIRST row (top row).

    Return ONLY this JSON:
    {
    "soat_numero": "policy number",
    "soat_expedicion": "expedition date DD/MM/YYYY",
    "soat_inicio": "start date DD/MM/YYYY",
    "soat_fin": "end date DD/MM/YYYY",
    "soat_aseguradora": "company name",
    "soat_estado": "VIGENTE or NO VIGENTE"
    }

    If table is empty: use "" and "NO VIGENTE" for estado."""
                        }]
                    }],
                    temperature=0.1,
                    max_tokens=200
                )
                
                respuesta = str(response.choices[0].message.content).strip()
                json_str = respuesta[respuesta.find("{"):respuesta.rfind("}")+1]
                datos_soat = json.loads(json_str)
                print(f"  ✅ SOAT: {datos_soat.get('soat_estado')} (hasta {datos_soat.get('soat_fin')})")
                
            except Exception as e:
                print(f"  ⚠️  Error SOAT: {str(e)[:50]}")
                datos_soat = {
                    'soat_numero': '', 'soat_expedicion': '', 'soat_inicio': '',
                    'soat_fin': '', 'soat_aseguradora': '', 'soat_estado': 'ERROR'
                }
            
            # ========== EXTRAE RTM ==========
            print("  🔧 Abriendo panel RTM...")
            driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(2)
            
            try:
                panel_rtm = driver.find_element(By.XPATH, "//mat-expansion-panel-header[.//mat-panel-title[contains(text(), 'técnico mecánica')]]")
                driver.execute_script("arguments[0].scrollIntoView(true);", panel_rtm)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", panel_rtm)
                time.sleep(4)
                print("  ✅ Panel RTM abierto")
                
                paso3_rtm = debug_path('paso3_rtm.png')
                driver.save_screenshot(paso3_rtm)
                with open(paso3_rtm, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                print("  🤖 Groq: Extrayendo RTM...")
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "system",
                        "content": "Extract RTM data from table. Return ONLY JSON."
                    }, {
                        "role": "user",
                        "content": [{
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }, {
                            "type": "text",
                            "text": """Find the RTM/Revisión técnico mecánica table. Extract ONLY the FIRST row.

    Return ONLY this JSON:
    {
    "rtm_numero": "certificate number",
    "rtm_vigencia": "validity date DD/MM/YYYY",
    "rtm_cda": "CDA name",
    "rtm_estado": "VIGENTE or NO VIGENTE"
    }

    If table is empty: use "" and "NO VIGENTE"."""
                        }]
                    }],
                    temperature=0.1,
                    max_tokens=200
                )
                
                respuesta = str(response.choices[0].message.content).strip()
                json_str = respuesta[respuesta.find("{"):respuesta.rfind("}")+1]
                datos_rtm = json.loads(json_str)
                print(f"  ✅ RTM: {datos_rtm.get('rtm_estado')} (hasta {datos_rtm.get('rtm_vigencia')})")
                
            except Exception as e:
                print(f"  ⚠️  Error RTM: {str(e)[:50]}")
                datos_rtm = {
                    'rtm_numero': '', 'rtm_vigencia': '', 'rtm_cda': '', 'rtm_estado': 'ERROR'
                }
            
            # ========== COMBINA DATOS ==========
            datos = {
                'placa': self.placa,
                'cedula': self.cedula,
                **datos_vehiculo,
                **datos_soat,
                **datos_rtm
            }
            
            return datos
            
        except Exception as e:
            print(f"  ⚠️  Error general: {str(e)[:80]}")
            return {
                'placa': self.placa, 'cedula': self.cedula,
                'marca': '', 'linea': '', 'modelo': '', 'color': '',
                'clase': '', 'tipo_servicio': '', 'estado': '', 'combustible': '',
                'soat_numero': '', 'soat_expedicion': '', 'soat_inicio': '', 'soat_fin': '', 'soat_aseguradora': '', 'soat_estado': 'ERROR',
                'rtm_numero': '', 'rtm_vigencia': '', 'rtm_cda': '', 'rtm_estado': 'ERROR'
            }


    
    def execute(self):
        driver = self.driver
        intentos_consulta = 5
        
        for intento_consulta in range(1, intentos_consulta + 1):
            try:
                print(f"  🌐 Cargando RUNT (intento {intento_consulta}/5)...")
                driver.get(RUNT_URL)
                time.sleep(5)
                
                if not EnterText.into(driver, self.placa, RuntScreen.placa_input):
                    continue
                
                SelectOption.cedula_ciudadania(driver, RuntScreen.tipo_doc_select)
                
                if not EnterText.into(driver, self.cedula, RuntScreen.cedula_input):
                    continue
                
                if not self.resolver_captcha_con_groq():
                    print("  ⚠️  No se ingresó CAPTCHA")
                    continue
                
                if not ClickOn.element(driver, RuntScreen.submit_btn):
                    continue
                
                # VALIDAR SI EL CAPTCHA FUE CORRECTO
                time.sleep(3)
                
                # Verifica si hay error de CAPTCHA
                try:
                    error_captcha = driver.find_element(By.XPATH, "//*[contains(text(), 'captcha no es valido') or contains(text(), 'CAPTCHA incorrecto')]")
                    print(f"  ❌ CAPTCHA INCORRECTO (intento {intento_consulta}/5)")
                    
                    # Cierra el modal de error si existe
                    try:
                        btn_aceptar = driver.find_element(By.XPATH, "//button[contains(text(), 'Aceptar')]")
                        btn_aceptar.click()
                        time.sleep(2)
                    except:
                        pass
                    
                    if intento_consulta < 5:
                        print("  🔄 Reintentando consulta...")
                        continue
                    else:
                        print("  ⚠️  Agotados los intentos de CAPTCHA")
                        return None
                        
                except:
                    # No hay error de CAPTCHA, continuar extrayendo datos
                    print("  ✅ CAPTCHA CORRECTO")
                    pass
                
                # Verifica que llegó a la página de resultados
                time.sleep(3)
                try:
                    driver.find_element(By.XPATH, "//*[contains(text(), 'MARCA') or contains(text(), 'Información general')]")
                    print("  ✅ Página de resultados cargada")
                except:
                    print(f"  ⚠️  No se cargó la página de resultados (intento {intento_consulta}/5)")
                    if intento_consulta < 5:
                        continue
                    else:
                        return None
                
                return self.extraer_datos_completos()
                
            except Exception as e:
                print(f"  ⚠️  Error en intento {intento_consulta}: {str(e)[:80]}")
                if intento_consulta < 5:
                    time.sleep(3)
                    continue
                else:
                    return None
        
        return None


# ===== Main =====
def procesar_consultas_runt():
    print("\n" + "="*70)
    print("🚗 BOT RUNT - Vehículo + SOAT + RTM")
    print("="*70 + "\n")
    
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        print("✅ Conectado a Sheets\n")
    except Exception as e:
        print(f"❌ {e}")
        return
    
    headers = ['placa', 'cedula', 'marca', 'linea', 'modelo', 'color', 'clase', 'tipo_servicio', 'estado', 'combustible',
               'soat_numero', 'soat_expedicion', 'soat_inicio', 'soat_fin', 'soat_aseguradora', 'soat_estado',
               'rtm_numero', 'rtm_vigencia', 'rtm_cda', 'rtm_estado']
    
    try:
        print("📝 Verificando encabezados...")
        primera_fila = sheet.row_values(1)
        
        if not primera_fila or len(primera_fila) != len(headers) or primera_fila != headers:
            print("  🔧 Corrigiendo encabezados...")
            sheet.update(values=[headers], range_name='A1:T1')
            print("  ✅ Encabezados actualizados")
        else:
            print("  ✅ Encabezados correctos")
    except Exception as e:
        print(f"  ⚠️  {e}")
    
    try:
        all_values = sheet.get_all_values()
        
        if len(all_values) <= 1:
            print("⚠️  No hay datos para procesar\n")
            return
        
        datos = []
        for row in all_values[1:]:
            if len(row) >= 2 and row[0] and row[1]:
                datos.append({'placa': row[0], 'cedula': row[1]})
        
        print(f"📋 Registros: {len(datos)}\n")
        
    except Exception as e:
        print(f"❌ Error leyendo datos: {e}")
        return
    
    if len(datos) == 0:
        print("⚠️  No hay registros")
        return
    
    print("🦊 Iniciando Firefox...")
    options = Options()
    if HEADLESS:
        options.add_argument("--headless")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
    driver = webdriver.Firefox(options=options)
    if not HEADLESS:
        driver.maximize_window()
    print("✅ Listo\n")
    
    try:
        for idx, row in enumerate(datos, start=2):
            placa = str(row.get('placa', '')).strip()
            cedula = str(row.get('cedula', '')).strip()
            
            if not placa or not cedula:
                continue
            
            print("\n" + "─"*70)
            print(f"🔍 FILA {idx}: {placa} | {cedula}")
            print("─"*70)
            
            task = ConsultarRuntTask(driver, placa, cedula)
            resultado = task.execute()
            
            if resultado:
                valores = [
                    resultado.get('placa', ''), resultado.get('cedula', ''),
                    resultado.get('marca', ''), resultado.get('linea', ''),
                    resultado.get('modelo', ''), resultado.get('color', ''),
                    resultado.get('clase', ''), resultado.get('tipo_servicio', ''),
                    resultado.get('estado', ''), resultado.get('combustible', ''),
                    resultado.get('soat_numero', ''), resultado.get('soat_expedicion', ''),
                    resultado.get('soat_inicio', ''), resultado.get('soat_fin', ''),
                    resultado.get('soat_aseguradora', ''), resultado.get('soat_estado', ''),
                    resultado.get('rtm_numero', ''), resultado.get('rtm_vigencia', ''),
                    resultado.get('rtm_cda', ''), resultado.get('rtm_estado', '')
                ]
                
                sheet.update(values=[valores], range_name=f'A{idx}:T{idx}')
                print(f"✅ {resultado.get('marca', '')} {resultado.get('modelo', '')} | SOAT:{resultado.get('soat_estado', '')} | RTM:{resultado.get('rtm_estado', '')}")
            
            time.sleep(3)
            
        print("\n✅ COMPLETADO\n")
    except KeyboardInterrupt:
        print("\n⚠️  Interrumpido")
    finally:
        driver.quit()

if __name__ == "__main__":
    procesar_consultas_runt()
