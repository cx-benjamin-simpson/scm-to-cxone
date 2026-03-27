import logging
import os  

def setup_logger(name='scm2cxone_logger', log_file='logs/log_scm2cxone.log', level=logging.DEBUG, enable_console=True, format_log=True):  
    
    logger = logging.getLogger(name)  
    logger.setLevel(level)  
    
    # Ensure the log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create file handler  
    file_handler = logging.FileHandler(log_file)  
    file_handler.setLevel(level)  
    
    if (enable_console):
        # Create console handler  
        console_handler = logging.StreamHandler()  
        console_handler.setLevel(logging.INFO)
    
    # Create a formatter and set it for handlers  
    if (format_log):
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')  
        file_handler.setFormatter(formatter)  
        if (enable_console):
            console_handler.setFormatter(formatter)  
    
    # Add handlers to the logger  
    if not logger.handlers:  # Prevent adding multiple handlers if setup_logger is called again  
        logger.addHandler(file_handler)  
        if (enable_console):
            logger.addHandler(console_handler)  
    
    return logger  

# Configure the logger 
logger = setup_logger()

# Configure the report logger
report_logger = setup_logger(name="report_scm2cxone", log_file='logs/report_scm2cxone.log', enable_console=False, format_log=False)