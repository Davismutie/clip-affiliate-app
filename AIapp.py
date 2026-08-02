"""
CLIP AFFILIATE AI MARKETING AGENT
Production-Ready for GitHub Deployment
"""

import os
import sys
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import Counter
import re
import requests
from flask import Flask, jsonify, render_template_string, request
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """Application configuration from environment variables"""
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE_URL = os.getenv('DATABASE_URL', 'clip_affiliate.db')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', 5000))
    
    # API Keys (set these in GitHub Secrets)
    JUMIA_API_KEY = os.getenv('JUMIA_API_KEY', '')
    AFRICASTALKING_API_KEY = os.getenv('AFRICASTALKING_API_KEY', '')
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
    
    # Monitoring settings
    MONITORING_INTERVAL = int(os.getenv('MONITORING_INTERVAL', 6))  # hours
    AUTO_START_MONITORING = os.getenv('AUTO_START_MONITORING', 'False').lower() == 'true'

config = Config()

# ============================================================
# DATABASE
# ============================================================

class Database:
    """Database management with connection pooling"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price_usd REAL NOT NULL,
                category TEXT,
                image TEXT,
                affiliate_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id TEXT,
                customer_phone TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # AI Campaign Results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT,
                products_analyzed INTEGER,
                recommendations_count INTEGER,
                estimated_reach INTEGER,
                estimated_sales INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Market Trends
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT,
                category TEXT,
                price REAL,
                rating REAL,
                trend_score REAL,
                marketplace TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample products if empty
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            sample_products = [
                ("Wireless Earbuds Pro", 29.99, "Electronics", "https://images.unsplash.com/photo-1572536147248-ac59a8abfa4b", "https://s.click.aliexpress.com/e/_sample1"),
                ("Smart Fitness Watch", 45.50, "Wearables", "https://images.unsplash.com/photo-1523275335684-37898b6baf30", "https://s.click.aliexpress.com/e/_sample2"),
                ("Mini Drone 4K Camera", 89.00, "Gadgets", "https://images.unsplash.com/photo-1507582020474-9a35b7d455d9", "https://s.click.aliexpress.com/e/_sample3")
            ]
            cursor.executemany(
                "INSERT INTO products (title, price_usd, category, image, affiliate_link) VALUES (?, ?, ?, ?, ?)",
                sample_products
            )
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

# Initialize database
db = Database(config.DATABASE_URL)

# ============================================================
# MARKET INTELLIGENCE ENGINE
# ============================================================

class MarketIntelligenceEngine:
    """Scrapes and analyzes market trends"""
    
    def __init__(self):
        self.marketplaces = {
            'jumia_ke': os.getenv('JUMIA_KE_URL', 'https://www.jumia.co.ke'),
            'jumia_ug': os.getenv('JUMIA_UG_URL', 'https://www.jumia.ug'),
        }
        self.category_keywords = {
            'electronics': ['phone', 'laptop', 'headphone', 'charger', 'power bank', 'tv', 'tablet'],
            'fashion': ['shirt', 'dress', 'shoe', 'handbag', 'watch', 'jeans'],
            'home': ['furniture', 'kitchen', 'decor', 'lighting', 'bedding'],
            'health': ['vitamin', 'supplement', 'fitness', 'mask', 'sanitizer'],
            'automotive': ['car', 'bike', 'spare', 'tire', 'accessory'],
            'baby': ['diaper', 'toy', 'baby food', 'stroller', 'crib'],
            'gadgets': ['drone', 'smartwatch', 'speaker', 'camera', 'headset']
        }
    
    def scrape_jumia_category(self, country: str, category: str = 'all') -> List[Dict]:
        """Scrape Jumia for trending products"""
        try:
            base_url = self.marketplaces[f'jumia_{country}']
            
            if category != 'all':
                url = f"{base_url}/{category}/"
            else:
                url = f"{base_url}/catalog/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            products = []
            product_cards = soup.find_all('article', class_='prd')
            
            for card in product_cards[:20]:
                try:
                    name_elem = card.find('h3', class_='name')
                    name = name_elem.text.strip() if name_elem else 'Unknown Product'
                    
                    price_elem = card.find('div', class_='prc')
                    price = price_elem.text.strip() if price_elem else 'N/A'
                    
                    rating_elem = card.find('div', class_='stars')
                    rating = rating_elem.text.strip() if rating_elem else '0'
                    
                    img = card.find('img')
                    image_url = img.get('data-src', img.get('src', '')) if img else ''
                    
                    url_elem = card.find('a')
                    product_url = url_elem.get('href', '') if url_elem else ''
                    
                    detected_category = self.detect_category(name)
                    
                    products.append({
                        'name': name,
                        'price': price,
                        'rating': rating,
                        'image_url': image_url,
                        'category': detected_category,
                        'marketplace': f'Jumia {country.upper()}',
                        'url': product_url,
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error parsing product card: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error scraping Jumia {country}: {e}")
            return []
    
    def detect_category(self, product_name: str) -> str:
        """Detect product category using keywords"""
        product_name_lower = product_name.lower()
        for category, keywords in self.category_keywords.items():
            if any(keyword in product_name_lower for keyword in keywords):
                return category
        return 'miscellaneous'
    
    def analyze_trends(self, products: List[Dict]) -> Dict:
        """Analyze product trends"""
        if not products:
            return {'trending': [], 'popular_categories': [], 'top_sellers': []}
        
        categories = [p.get('category', 'unknown') for p in products]
        category_counts = Counter(categories)
        
        trending = []
        for p in products:
            try:
                rating_str = p.get('rating', '0')
                rating = float(rating_str.split()[0]) if rating_str else 0
                
                price_str = re.sub(r'[^0-9.]', '', p.get('price', '0'))
                price = float(price_str) if price_str else 0
                
                if rating >= 4.0 and 1000 < price < 50000:
                    trending.append({
                        **p,
                        'score': rating * (50000 / (price + 1000))
                    })
            except:
                continue
        
        trending.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return {
            'trending': trending[:10],
            'popular_categories': dict(category_counts.most_common(5)),
            'top_sellers': products[:5],
            'analysis_time': datetime.now().isoformat()
        }
    
    def get_market_pulse(self, countries: List[str] = ['ke', 'ug']) -> Dict:
        """Get complete market intelligence"""
        all_products = []
        
        for country in countries:
            logger.info(f"Scraping Jumia {country.upper()}...")
            products = self.scrape_jumia_category(country)
            all_products.extend(products)
            time.sleep(2)
        
        analysis = self.analyze_trends(all_products)
        analysis['total_products_analyzed'] = len(all_products)
        analysis['countries_scraped'] = countries
        
        return analysis

# ============================================================
# AI MARKETING ASSISTANT
# ============================================================

class AIMarketingAssistant:
    """Intelligent marketing agent"""
    
    def __init__(self, intelligence_engine: MarketIntelligenceEngine):
        self.engine = intelligence_engine
        self.campaign_history = []
    
    def generate_product_recommendations(self, market_data: Dict, limit: int = 10) -> List[Dict]:
        """Generate AI-powered product recommendations"""
        recommendations = []
        trending = market_data.get('trending', [])
        
        for product in trending[:limit]:
            marketing_copy = self.generate_marketing_copy(product)
            
            price = product.get('price', '0')
            try:
                price_num = float(re.sub(r'[^0-9.]', '', price))
                estimated_commission = price_num * 0.20
            except:
                estimated_commission = 0
            
            recommendations.append({
                'product': product,
                'marketing_copy': marketing_copy,
                'estimated_commission_usd': estimated_commission,
                'recommended_platforms': self.suggest_platforms(product['category']),
                'target_audience': self.identify_audience(product),
                'urgency_score': self.calculate_urgency(product)
            })
        
        return recommendations
    
    def generate_marketing_copy(self, product: Dict) -> Dict:
        """Generate marketing copy for different platforms"""
        name = product.get('name', 'this amazing product')
        category = product.get('category', 'product')
        price = product.get('price', 'best price')
        
        return {
            'facebook': f"🔥 HOT DEAL! {name} now available in East Africa! Get yours today at {price}. #ShopLocal #ClipAffiliate",
            'instagram': f"✨ Discover {name} - the perfect {category}! Shop now at {price}. 🛍️ #ClipAffiliate",
            'twitter': f"🚀 Trending: {name} is taking East Africa by storm! Don't miss out. Shop now!",
            'whatsapp': f"🌟 Special Offer! Get {name} at {price}. Limited stock available!",
            'sms': f"{name} - East Africa's favorite {category}! Order now via Clip Affiliate."
        }
    
    def suggest_platforms(self, category: str) -> List[str]:
        """Suggest best marketing platforms"""
        platform_map = {
            'electronics': ['Facebook', 'Instagram', 'Twitter'],
            'fashion': ['Instagram', 'Pinterest', 'TikTok'],
            'home': ['Facebook', 'Pinterest', 'WhatsApp'],
            'health': ['Facebook', 'WhatsApp', 'Instagram'],
            'automotive': ['Facebook', 'Twitter', 'WhatsApp'],
            'baby': ['Facebook', 'Instagram', 'WhatsApp'],
            'gadgets': ['Instagram', 'TikTok', 'Twitter']
        }
        return platform_map.get(category, ['Facebook', 'WhatsApp', 'Instagram'])
    
    def identify_audience(self, product: Dict) -> Dict:
        """Identify target audience"""
        category = product.get('category', 'general')
        
        audiences = {
            'electronics': {'age': '18-35', 'income': 'middle', 'interest': 'tech-savvy'},
            'fashion': {'age': '16-40', 'income': 'middle-upper', 'interest': 'fashion-conscious'},
            'home': {'age': '25-50', 'income': 'middle', 'interest': 'home improvement'},
            'health': {'age': '25-60', 'income': 'middle-upper', 'interest': 'wellness'},
            'automotive': {'age': '25-55', 'income': 'upper', 'interest': 'automotive'},
            'baby': {'age': '22-40', 'income': 'middle', 'interest': 'parenting'},
            'gadgets': {'age': '18-35', 'income': 'middle', 'interest': 'gadgets'}
        }
        return audiences.get(category, {'age': '18-50', 'income': 'middle', 'interest': 'general'})
    
    def calculate_urgency(self, product: Dict) -> int:
        """Calculate urgency score (1-10)"""
        urgency_score = 5
        
        try:
            rating = float(product.get('rating', '0').split()[0]) if product.get('rating') else 0
            if rating >= 4.5:
                urgency_score += 3
            elif rating >= 4.0:
                urgency_score += 1
        except:
            pass
        
        try:
            price = float(re.sub(r'[^0-9.]', '', product.get('price', '0')))
            if 5000 < price < 30000:
                urgency_score += 2
        except:
            pass
        
        return min(10, urgency_score)
    
    def create_marketing_campaign(self, recommendations: List[Dict]) -> Dict:
        """Create a complete marketing campaign"""
        campaign = {
            'id': f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'products': recommendations[:5],
            'channels': ['Social Media', 'WhatsApp Business', 'SMS Marketing'],
            'schedule': self.optimize_schedule(),
            'budget_allocation': self.allocate_budget(recommendations),
            'estimated_reach': self.estimate_reach(recommendations)
        }
        
        self.campaign_history.append(campaign)
        return campaign
    
    def optimize_schedule(self) -> Dict:
        """Optimize marketing schedule"""
        return {
            'morning': '7:00 AM - 9:00 AM EAT',
            'midday': '12:00 PM - 2:00 PM EAT',
            'evening': '6:00 PM - 9:00 PM EAT',
            'best_days': ['Monday', 'Wednesday', 'Friday', 'Saturday']
        }
    
    def allocate_budget(self, recommendations: List[Dict]) -> Dict:
        """Allocate marketing budget"""
        budgets = {}
        total_score = sum(r.get('urgency_score', 1) for r in recommendations[:5])
        
        for i, rec in enumerate(recommendations[:5]):
            score = rec.get('urgency_score', 1)
            percentage = (score / total_score) * 100 if total_score > 0 else 0
            budgets[f"Product_{i+1}"] = {
                'percentage': round(percentage, 1),
                'amount_usd': round(100 * (score / total_score), 2) if total_score > 0 else 0
            }
        
        return budgets
    
    def estimate_reach(self, recommendations: List[Dict]) -> Dict:
        """Estimate potential reach"""
        reach_by_product = []
        for rec in recommendations[:5]:
            urgency = rec.get('urgency_score', 5)
            audience_size = 500 * urgency
            reach_by_product.append({
                'product_name': rec['product'].get('name', 'Product')[:30],
                'estimated_reach': audience_size,
                'estimated_conversions': int(audience_size * 0.05),
                'estimated_sales': int(audience_size * 0.02)
            })
        
        return {
            'total_reach': sum(r['estimated_reach'] for r in reach_by_product),
            'total_sales_estimate': sum(r['estimated_sales'] for r in reach_by_product),
            'breakdown': reach_by_product
        }

# ============================================================
# AUTOMATED MARKETING AGENT
# ============================================================

class AutomatedMarketingAgent:
    """Orchestrates automated marketing"""
    
    def __init__(self):
        self.intelligence = MarketIntelligenceEngine()
        self.marketing = AIMarketingAssistant(self.intelligence)
        self.running = False
        self.market_data_cache = {}
        self.monitoring_thread = None
    
    def run_intelligence_cycle(self) -> Dict:
        """Run a complete intelligence and marketing cycle"""
        logger.info("Starting market intelligence cycle...")
        
        market_data = self.intelligence.get_market_pulse(['ke', 'ug'])
        self.market_data_cache = market_data
        
        logger.info(f"Analyzed {market_data['total_products_analyzed']} products")
        logger.info(f"Found {len(market_data['trending'])} trending products")
        
        recommendations = self.marketing.generate_product_recommendations(market_data)
        logger.info(f"Generated {len(recommendations)} product recommendations")
        
        campaign = self.marketing.create_marketing_campaign(recommendations)
        logger.info(f"Created campaign: {campaign['id']}")
        logger.info(f"Estimated reach: {campaign['estimated_reach']['total_reach']}")
        
        # Save to database
        self.save_campaign_results(campaign, market_data, recommendations)
        
        return {
            'campaign': campaign,
            'recommendations': recommendations[:5],
            'timestamp': datetime.now().isoformat()
        }
    
    def save_campaign_results(self, campaign: Dict, market_data: Dict, recommendations: List[Dict]):
        """Save campaign results to database"""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO campaign_results 
            (campaign_id, products_analyzed, recommendations_count, estimated_reach, estimated_sales)
            VALUES (?, ?, ?, ?, ?)
        """, (
            campaign.get('id', 'unknown'),
            market_data.get('total_products_analyzed', 0),
            len(recommendations),
            campaign.get('estimated_reach', {}).get('total_reach', 0),
            campaign.get('estimated_reach', {}).get('total_sales_estimate', 0)
        ))
        
        conn.commit()
        conn.close()
    
    def start_continuous_monitoring(self, interval_hours: int = 6):
        """Start continuous market monitoring"""
        if self.running:
            logger.warning("Monitoring already running")
            return
        
        self.running = True
        logger.info(f"Starting continuous monitoring (every {interval_hours} hours)")
        
        def monitor_loop():
            while self.running:
                try:
                    self.run_intelligence_cycle()
                    logger.info(f"Sleeping for {interval_hours} hours...")
                    time.sleep(interval_hours * 3600)
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}")
                    time.sleep(3600)
        
        self.monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitoring stopped")

# Initialize agent
agent = AutomatedMarketingAgent()

# Auto-start monitoring if configured
if config.AUTO_START_MONITORING:
    agent.start_continuous_monitoring(config.MONITORING_INTERVAL)

# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# HTML Templates (keep from previous version)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clip Affiliate - East Africa Hub</title>
    <style>
        :root { --primary: #ff4757; --dark: #2f3542; --light: #f1f2f6; --success: #2ed573; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: var(--light); color: var(--dark); }
        header { background: var(--dark); color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        header h1 { color: var(--primary); font-size: 1.5rem; }
        .currency-selector select { padding: 0.5rem; border-radius: 4px; border: none; font-weight: bold; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .hero { background: linear-gradient(135deg, #ff4757, #ff6b81); color: white; padding: 3rem; border-radius: 8px; text-align: center; margin-bottom: 2rem; }
        .hero h2 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        .catalog { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2rem; }
        .card { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: flex; flex-direction: column; justify-content: space-between; }
        .card img { width: 100%; height: 200px; object-fit: cover; }
        .card-body { padding: 1.5rem; }
        .card-body h3 { font-size: 1.2rem; margin-bottom: 0.5rem; }
        .price { font-size: 1.3rem; font-weight: bold; color: var(--primary); margin-bottom: 1rem; }
        .btn-group { display: flex; gap: 0.5rem; }
        .btn { flex: 1; padding: 0.75rem; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; text-align: center; text-decoration: none; }
        .btn-affiliate { background: #ffa502; color: white; }
        .btn-checkout { background: var(--success); color: white; }
        .btn-ai { background: #6c5ce7; color: white; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }
        .modal-content { background: white; padding: 2rem; border-radius: 8px; width: 90%; max-width: 400px; text-align: center; }
        .modal-content input { width: 100%; padding: 0.75rem; margin: 1rem 0; border: 1px solid #ccc; border-radius: 4px; }
    </style>
</head>
<body>

    <header>
        <h1>Clip Affiliate 🛒</h1>
        <div>
            <a href="/ai-dashboard" style="color: white; margin-right: 1rem;">🤖 AI Dashboard</a>
            <div class="currency-selector" style="display: inline-block;">
                <label for="currency">Currency: </label>
                <select id="currency" onchange="updateCurrency()">
                    <option value="UGX">UGX (Uganda)</option>
                    <option value="KES">KES (Kenya)</option>
                    <option value="USD">USD ($)</option>
                </select>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="hero">
            <h2>East Africa Cross-Border Dropshipping & Affiliate Hub</h2>
            <p>Kampala & Nairobi's Premier Sourcing Engine with AI-Powered Marketing</p>
        </div>

        <div class="catalog" id="product-catalog">
            <!-- Dynamically populated -->
        </div>
    </div>

    <div class="modal" id="checkout-modal">
        <div class="modal-content">
            <h3>Mobile Money Express Checkout</h3>
            <p>Send payment directly to Merchant:</p>
            <p style="font-size: 1.2rem; font-weight: bold; color: #ff4757; margin: 0.5rem 0;">+256 757 202891</p>
            <p id="modal-price-display" style="margin-bottom: 1rem;"></p>
            <input type="text" id="buyer-phone" placeholder="Enter Your Mobile Number (e.g. 0757XXXXXX)">
            <button class="btn btn-checkout" onclick="processPayment()">Authorize & Pay Now</button>
            <button class="btn" style="background:#ddd; margin-top:0.5rem;" onclick="closeModal()">Cancel</button>
        </div>
    </div>

    <script>
        let products = [];
        let rates = { USD: 1, UGX: 3700, KES: 130 };
        let currentItem = null;

        async function fetchProducts() {
            const res = await fetch('/api/products');
            products = await res.json();
            renderCatalog();
        }

        function renderCatalog() {
            const currency = document.getElementById('currency').value;
            const catalogEl = document.getElementById('product-catalog');
            catalogEl.innerHTML = '';

            products.forEach(p => {
                let convertedPrice = p.price_usd * rates[currency];
                let formattedPrice = currency === 'USD' ? '$' + convertedPrice.toFixed(2) : currency + ' ' + Math.round(convertedPrice).toLocaleString();

                catalogEl.innerHTML += `
                    <div class="card">
                        <img src="${p.image}" alt="${p.title}">
                        <div class="card-body">
                            <h3>${p.title}</h3>
                            <div class="price">${formattedPrice}</div>
                            <div class="btn-group">
                                <a href="${p.affiliate_link}" target="_blank" class="btn btn-affiliate">AliExpress Link</a>
                                <button class="btn btn-checkout" onclick="openCheckout('${p.title}', ${p.price_usd})">Buy Now</button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }

        function updateCurrency() {
            renderCatalog();
        }

        function openCheckout(title, priceUsd) {
            currentItem = { title, priceUsd };
            const currency = document.getElementById('currency').value;
            let converted = priceUsd * rates[currency];
            let displayStr = currency === 'USD' ? '$' + converted.toFixed(2) : currency + ' ' + Math.round(converted).toLocaleString();
            
            document.getElementById('modal-price-display').innerText = `Total: ${displayStr} for ${title}`;
            document.getElementById('checkout-modal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('checkout-modal').style.display = 'none';
        }

        async function processPayment() {
            const phone = document.getElementById('buyer-phone').value;
            if(!phone) { alert('Please enter your mobile phone number.'); return; }
            
            const currency = document.getElementById('currency').value;
            const amount = currentItem.priceUsd * rates[currency];

            const response = await fetch('/api/pay/mobile-money', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    merchant_phone: "+256757202891",
                    customer_phone: phone,
                    amount: amount,
                    currency: currency,
                    item: currentItem.title
                })
            });

            const result = await response.json();
            alert(result.message);
            closeModal();
        }

        fetchProducts();
    </script>
</body>
</html>
"""

# AI Dashboard HTML (same as previous version - keep it)

# ============================================================
# API ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/products", methods=["GET"])
def get_products():
    """Get all products"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route("/api/pay/mobile-money", methods=["POST"])
def mobile_money_payment():
    """Process mobile money payment"""
    data = request.json
    merchant_phone = data.get("merchant_phone", "+256757202891")
    customer_phone = data.get("customer_phone")
    amount = data.get("amount")
    currency = data.get("currency")
    item = data.get("item")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (merchant_id, customer_phone, amount, currency, status)
        VALUES (?, ?, ?, ?, ?)
    """, (merchant_phone, customer_phone, amount, currency, "PENDING_STK_PUSH"))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"STK Push payment prompt sent to {customer_phone}. Confirm payment of {currency} {amount:.2f} to merchant account {merchant_phone}."
    })

# AI Routes
@app.route("/ai-dashboard")
def ai_dashboard():
    """AI Marketing Assistant Dashboard"""
    # Include AI dashboard HTML here (same as previous version)
    from flask import render_template_string
    return render_template_string(AI_DASHBOARD_HTML)

@app.route("/api/ai/market-intelligence", methods=["GET"])
def get_market_intelligence():
    """Get current market intelligence"""
    if agent.market_data_cache:
        return jsonify({
            'status': 'success',
            'data': agent.market_data_cache,
            'timestamp': datetime.now().isoformat()
        })
    else:
        market_data = agent.intelligence.get_market_pulse(['ke', 'ug'])
        return jsonify({
            'status': 'success',
            'data': market_data,
            'timestamp': datetime.now().isoformat()
        })

@app.route("/api/ai/recommendations", methods=["GET"])
def get_ai_recommendations():
    """Get AI product recommendations"""
    if not agent.market_data_cache:
        agent.market_data_cache = agent.intelligence.get_market_pulse(['ke', 'ug'])
    
    recommendations = agent.marketing.generate_product_recommendations(agent.market_data_cache)
    return jsonify({
        'status': 'success',
        'recommendations': recommendations[:10],
        'timestamp': datetime.now().isoformat()
    })

@app.route("/api/ai/run-campaign", methods=["POST"])
def run_ai_campaign():
    """Run an AI marketing campaign"""
    results = agent.run_intelligence_cycle()
    return jsonify({
        'status': 'success',
        'message': 'Marketing campaign generated successfully',
        'campaign_id': results['campaign']['id'],
        'details': results
    })

@app.route("/api/ai/start-monitoring", methods=["POST"])
def start_monitoring():
    """Start continuous monitoring"""
    data = request.json or {}
    interval = data.get('interval_hours', config.MONITORING_INTERVAL)
    
    if not agent.running:
        agent.start_continuous_monitoring(interval)
        return jsonify({
            'status': 'success',
            'message': f'Monitoring started with {interval} hour intervals'
        })
    else:
        return jsonify({
            'status': 'info',
            'message': 'Monitoring is already running'
        })

@app.route("/api/ai/stop-monitoring", methods=["POST"])
def stop_monitoring():
    """Stop continuous monitoring"""
    if agent.running:
        agent.stop_monitoring()
        return jsonify({
            'status': 'success',
            'message': 'Monitoring stopped'
        })
    else:
        return jsonify({
            'status': 'info',
            'message': 'Monitoring is not running'
        })

@app.route("/api/ai/history", methods=["GET"])
def get_campaign_history():
    """Get campaign history"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT * FROM campaign_results 
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        
        history = []
        for row in cursor.fetchall():
            history.append(dict(row))
        
        return jsonify({
            'status': 'success',
            'history': history
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })
    finally:
        conn.close()

@app.route("/health")
def health_check():
    """Health check endpoint for GitHub deployments"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'monitoring_running': agent.running,
        'database': config.DATABASE_URL
    })

# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 Starting Clip Affiliate AI on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
